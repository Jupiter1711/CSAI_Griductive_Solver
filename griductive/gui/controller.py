import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from griductive.agent.inference import LogicAgent
from griductive.agent.runner import DeductionRunner
from griductive.agent.trace import DeductionStep
from griductive.engine import GameEngine
from griductive.gui.highlight import ClueFocus, clue_focus, related_clue
from griductive.gui.text import (
    cell_label,
    character_name,
    describe_clue,
    run_status_message,
    submit_message,
)
from griductive.models import (
    Cell,
    Classification,
    ClassificationResult,
    Clue,
    EncodedKB,
    PublicState,
    RunStatus,
    SATQuery,
    Status,
    SubmitResult,
    SubmitStatus,
)
from griductive.puzzle_io import PuzzleLoader
from griductive.regions import RegionResolver


class MessageKind(str, Enum):
    INFO = "INFO"
    BUSY = "WORKING"
    HINT = "HINT"
    ACCEPTED = "ACCEPTED"
    NOT_PROVABLE = "NOT_PROVABLE"
    CONTRADICTED = "CONTRADICTED"
    ALREADY_REVEALED = "ALREADY_REVEALED"
    INCONSISTENT = "INCONSISTENT"
    SOLVED = "SOLVED"
    STUCK = "STUCK"
    ERROR = "ERROR"


_SUBMIT_KINDS = {
    SubmitStatus.ACCEPTED: MessageKind.ACCEPTED,
    SubmitStatus.NOT_PROVABLE: MessageKind.NOT_PROVABLE,
    SubmitStatus.CONTRADICTED: MessageKind.CONTRADICTED,
    SubmitStatus.ALREADY_REVEALED: MessageKind.ALREADY_REVEALED,
    SubmitStatus.INCONSISTENT: MessageKind.INCONSISTENT,
}

_RUN_KINDS = {
    RunStatus.RUNNING: MessageKind.ACCEPTED,
    RunStatus.SOLVED: MessageKind.SOLVED,
    RunStatus.STUCK: MessageKind.STUCK,
    RunStatus.INCONSISTENT: MessageKind.INCONSISTENT,
}


@dataclass(frozen=True)
class Message:
    kind: MessageKind
    text: str


@dataclass(frozen=True)
class Hint:
    status: RunStatus
    cell: Cell | None = None
    classification: Classification | None = None
    clue_id: str | None = None


@dataclass(frozen=True)
class SolverInfo:
    sat_calls: int = 0
    decisions: int = 0
    propagations: int = 0
    backtracks: int = 0
    runtime_s: float = 0.0
    primary: int = 0
    auxiliary: int = 0
    clauses: int = 0


Post = Callable[[Callable[[], None]], None]


class GameController:
    def __init__(
        self,
        engine: GameEngine,
        agent: LogicAgent,
        runner: DeductionRunner,
        loader: PuzzleLoader,
        regions: RegionResolver,
        step_delay: float = 0.45,
    ) -> None:
        self.engine = engine
        self.agent = agent
        self.runner = runner
        self.loader = loader
        self.regions = regions
        self.step_delay = step_delay

        self.state: PublicState | None = None
        self.puzzle_name: str | None = None
        self.selected_cell: Cell | None = None
        self.selected_clue_id: str | None = None
        self.hint: Hint | None = None
        self.message = Message(MessageKind.INFO, "Press Load to choose a puzzle.")
        self.log: list[str] = []
        self.info = SolverInfo()
        self.run_status: RunStatus | None = None
        self.reveal_times: dict[Cell, float] = {}
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.rejection: tuple[Cell, float] | None = None
        self.auto_running = False
        self.job_name: str | None = None

        self._steps = 0
        self._results: queue.Queue[Callable[[], None]] = queue.Queue()
        self._job: threading.Thread | None = None
        self._cancel = threading.Event()
        self._focus_cache: tuple[PublicState, str, ClueFocus] | None = None

    # Queries used by the renderer

    @property
    def busy(self) -> bool:
        return self._job is not None

    @property
    def solved(self) -> bool:
        if self.state is None:
            return False
        known = {verdict.cell for verdict in self.state.verdicts}
        return all(character.cell in known for character in self.state.board.characters)

    def verdict_of(self, cell: Cell) -> Status | None:
        if self.state is None:
            return None
        for verdict in self.state.verdicts:
            if verdict.cell == cell:
                return verdict.status
        return None

    def clue_of_owner(self, cell: Cell) -> Clue | None:
        if self.state is None:
            return None
        for clue in self.state.clues:
            if clue.owner == cell:
                return clue
        return None

    def is_face_up(self, cell: Cell) -> bool:
        return self.verdict_of(cell) is not None or self.clue_of_owner(cell) is not None

    def selected_clue(self) -> Clue | None:
        if self.state is None or self.selected_clue_id is None:
            return None
        return next(
            (clue for clue in self.state.clues if clue.id == self.selected_clue_id),
            None,
        )

    def focus(self) -> ClueFocus | None:
        clue = self.selected_clue()
        if clue is None or self.state is None:
            return None
        cached = self._focus_cache
        if cached and cached[0] is self.state and cached[1] == clue.id:
            return cached[2]
        try:
            focus = clue_focus(clue, self.state.board, self.regions)
        except (ValueError, NotImplementedError) as exc:
            self._set_message(MessageKind.ERROR, f"Cannot highlight clue: {exc}")
            focus = ClueFocus(())
        self._focus_cache = (self.state, clue.id, focus)
        return focus

    def describe(self, clue: Clue) -> str:
        assert self.state is not None
        return describe_clue(clue, self.state.board)

    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return max(0.0, end - self.started_at)

    def can_submit(self) -> bool:
        return (
            not self.busy
            and self.state is not None
            and self.selected_cell is not None
            and self.verdict_of(self.selected_cell) is None
        )

    # Selection (UI thread only, never blocks)

    def select_cell(self, cell: Cell | None) -> None:
        self.selected_cell = cell

    def move_selection(self, d_row: int, d_col: int) -> None:
        if self.state is None:
            return
        size = self.state.board.size
        current = self.selected_cell or Cell(0, 0)
        if self.selected_cell is not None:
            current = Cell(
                min(size - 1, max(0, current.row + d_row)),
                min(size - 1, max(0, current.col + d_col)),
            )
        self.selected_cell = current

    def select_clue(self, clue_id: str | None) -> None:
        self.selected_clue_id = None if clue_id == self.selected_clue_id else clue_id

    # Commands (each starts at most one background job)

    def load(self, path: Path) -> bool:
        def work(post: Post) -> None:
            puzzle = self.loader.load(path)
            state = self.engine.load(puzzle)
            post(lambda: self._apply_new_game(state, path.stem, "Loaded"))

        return self._start("Loading", work)

    def restart(self) -> bool:
        if self.state is None:
            self._set_message(MessageKind.INFO, "Load a puzzle first.")
            return False

        def work(post: Post) -> None:
            state = self.engine.restart()
            post(lambda: self._apply_new_game(state, self.puzzle_name, "Restarted"))

        return self._start("Restarting", work)

    def submit(self, status: Status) -> bool:
        if self.state is None or self.selected_cell is None:
            self._set_message(MessageKind.INFO, "Select a face-down card first.")
            return False
        cell = self.selected_cell
        if self.verdict_of(cell) is not None:
            name = character_name(self.state.board, cell)
            self._set_message(MessageKind.ALREADY_REVEALED, f"{name} is already known.")
            return False

        def work(post: Post) -> None:
            result = self.engine.submit(cell, status)
            post(lambda: self._apply_submit(cell, status, result))

        return self._start("Judging", work)

    def request_hint(self) -> bool:
        if self.state is None:
            self._set_message(MessageKind.INFO, "Load a puzzle first.")
            return False
        state = self.state

        def work(post: Post) -> None:
            analysis = self.agent.classify(state)
            post(lambda: self._apply_hint(state, analysis))

        return self._start("Thinking", work)

    def toggle_auto(self) -> bool:
        if self.auto_running:
            self._cancel.set()
            self._set_message(MessageKind.BUSY, "Stopping after the current step...")
            return True
        if self.state is None:
            self._set_message(MessageKind.INFO, "Load a puzzle first.")
            return False
        if self.solved:
            self._set_message(MessageKind.SOLVED, run_status_message(RunStatus.SOLVED))
            return False
        first = self._steps + 1

        def work(post: Post) -> None:
            number = first
            while not self._cancel.is_set():
                step = self.runner.step(self.engine, self.agent, number)
                post(lambda step=step: self._apply_step(step))
                if step.status is not RunStatus.RUNNING:
                    return
                number += 1
                self._cancel.wait(self.step_delay)

        started = self._start("Auto solving", work)
        self.auto_running = started
        return started

    # Job plumbing

    def poll(self) -> None:
        while True:
            try:
                apply = self._results.get_nowait()
            except queue.Empty:
                return
            apply()

    def wait(self, timeout: float = 10.0) -> None:
        job = self._job
        if job is not None:
            job.join(timeout)
            if job.is_alive():
                raise TimeoutError(f"{self.job_name} did not finish in {timeout}s")
        self.poll()

    def shutdown(self) -> None:
        self._cancel.set()

    def _start(self, name: str, work: Callable[[Post], None]) -> bool:
        if self.busy:
            return False
        self._cancel.clear()
        self.job_name = name

        def target() -> None:
            try:
                work(self._results.put)
            except Exception as exc:  # shown to the user, never swallowed silently
                self._results.put(lambda error=exc: self._fail(error))
            finally:
                self._results.put(self._finish)

        self._job = threading.Thread(
            target=target, name=f"griductive-{name}", daemon=True
        )
        self._job.start()
        return True

    def _finish(self) -> None:
        self._job = None
        self.job_name = None
        if self.auto_running and self._cancel.is_set() and not self._terminal():
            self._set_message(MessageKind.INFO, "Auto Solve stopped.")
        self.auto_running = False

    def _terminal(self) -> bool:
        return self.run_status in (
            RunStatus.SOLVED,
            RunStatus.STUCK,
            RunStatus.INCONSISTENT,
        )

    def _fail(self, exc: Exception) -> None:
        if isinstance(exc, NotImplementedError):
            text = "A module this action needs is not implemented yet."
        else:
            text = f"{type(exc).__name__}: {exc}"
        self._set_message(MessageKind.ERROR, text)
        self.log.append(f"Error: {text}")

    # Applying results (UI thread)

    def _set_message(self, kind: MessageKind, text: str) -> None:
        self.message = Message(kind, text)

    def _set_state(self, state: PublicState, animate: bool = True) -> None:
        before = set() if self.state is None else self._face_up_cells(self.state)
        after = self._face_up_cells(state)
        now = time.monotonic()
        if animate:
            for cell in after - before:
                self.reveal_times[cell] = now
        self.state = state
        self.hint = None  # a hint describes the previous snapshot only
        if self.solved and self.finished_at is None and self.started_at is not None:
            self.finished_at = time.monotonic()

    @staticmethod
    def _face_up_cells(state: PublicState) -> set[Cell]:
        cells = {verdict.cell for verdict in state.verdicts}
        return cells | {clue.owner for clue in state.clues}

    def _record(self, queries: tuple[SATQuery, ...], kb: EncodedKB | None) -> None:
        info = self.info
        for query in queries:
            stats = query.result.stats
            info = replace(
                info,
                sat_calls=info.sat_calls + 1,
                decisions=info.decisions + stats.decisions,
                propagations=info.propagations + stats.propagations,
                backtracks=info.backtracks + stats.backtracks,
                runtime_s=info.runtime_s + stats.runtime_s,
            )
        if kb is not None:
            info = replace(
                info,
                primary=len(kb.variables.primary),
                auxiliary=kb.variables.auxiliary_count,
                clauses=len(kb.cnf),
            )
        self.info = info

    def _apply_new_game(self, state: PublicState, name: str | None, verb: str) -> None:
        self.state = None
        self.reveal_times.clear()
        self._set_state(state)
        self.puzzle_name = name
        self.started_at = time.monotonic()
        self.finished_at = self.started_at if self.solved else None
        self.rejection = None
        self.selected_cell = None
        self.selected_clue_id = None
        self.info = SolverInfo()
        self.run_status = RunStatus.SOLVED if self.solved else RunStatus.RUNNING
        self.log = [f"{verb} {name}: {len(state.clues)} clue(s) face-up."]
        self._steps = 0
        if self.solved:
            self._set_message(MessageKind.SOLVED, run_status_message(RunStatus.SOLVED))
            return
        self._set_message(
            MessageKind.INFO,
            f"{verb} {name}. Pick a card and call CRIMINAL or INNOCENT.",
        )

    def _apply_submit(self, cell: Cell, status: Status, result: SubmitResult) -> None:
        assert self.state is not None
        board = self.state.board
        self._record(result.queries, result.kb)
        kind = _SUBMIT_KINDS.get(result.status, MessageKind.ERROR)
        text = submit_message(result, board, cell, status)
        self.log.append(
            f"You: {cell_label(cell)} {status.value} -> {result.status.value}"
        )
        if result.status in (SubmitStatus.NOT_PROVABLE, SubmitStatus.CONTRADICTED):
            self.rejection = (cell, time.monotonic())
        if result.status is SubmitStatus.ACCEPTED:
            self._set_state(result.state)
            self._steps += 1
            if result.revealed_clue is not None:
                self.selected_clue_id = result.revealed_clue.id
                text += f' New clue: "{self.describe(result.revealed_clue)}"'
            if self.solved:
                self.run_status = RunStatus.SOLVED
                kind, text = MessageKind.SOLVED, run_status_message(RunStatus.SOLVED)
        self._set_message(kind, text)

    def _apply_hint(self, asked: PublicState, analysis: ClassificationResult) -> None:
        if asked is not self.state:
            return  # state changed while thinking; the hint would be stale
        self._record(analysis.queries, analysis.kb)
        board = asked.board
        forced = next(
            (
                item
                for item in analysis.cells
                if item.classification is not Classification.UNKNOWN
            ),
            None,
        )
        if forced is None:
            self.hint = Hint(analysis.status)
            kind = _RUN_KINDS.get(analysis.status, MessageKind.INFO)
            if analysis.status is RunStatus.RUNNING:
                kind = MessageKind.STUCK
            self._set_message(kind, run_status_message(analysis.status))
            return

        clue = related_clue(forced.cell, asked.clues, board, self.regions)
        self.hint = Hint(
            analysis.status,
            forced.cell,
            forced.classification,
            None if clue is None else clue.id,
        )
        self.selected_cell = forced.cell
        name = character_name(board, forced.cell)
        text = f"{name} ({cell_label(forced.cell)}) can be proven now."
        if clue is not None:
            owner = character_name(board, clue.owner)
            text += f' Look at {owner}\'s clue: "{self.describe(clue)}"'
            self.selected_clue_id = clue.id
        self._set_message(MessageKind.HINT, text)

    def _apply_step(self, step: DeductionStep) -> None:
        board = step.state.board
        self._record(step.analysis.queries, step.analysis.kb)
        if step.submission is not None:
            self._record(step.submission.queries, None)
        self._set_state(step.state)
        self.run_status = step.status
        self._steps = step.number

        if step.verdict is None:
            text = run_status_message(step.status)
            self.log.append(f"Step {step.number}: {step.status.value}")
            self._set_message(_RUN_KINDS[step.status], text)
            return

        cell = step.verdict.cell
        name = character_name(board, cell)
        verdict = step.verdict.status.value
        line = f"Step {step.number}: {cell_label(cell)} {name} is {verdict}"
        clue = None if step.submission is None else step.submission.revealed_clue
        self.selected_cell = cell
        if clue is not None:
            self.selected_clue_id = clue.id
            line += f' | new clue: "{describe_clue(clue, board)}"'
        self.log.append(line)
        if step.status is RunStatus.RUNNING:
            self._set_message(MessageKind.ACCEPTED, line)
        else:
            self._set_message(_RUN_KINDS[step.status], run_status_message(step.status))
