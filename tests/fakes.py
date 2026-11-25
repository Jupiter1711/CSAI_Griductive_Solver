"""Brute-force stand-ins for the GUI tests and the preview script.

These are NOT the project's solver. They enumerate every assignment of the
unknown cells, which is fine for 3x3/4x4 demo boards and lets the GUI be built
and tested before the real encoder/DPLL/engine/runner are implemented. Swap in
the real classes in main.py once they exist.
"""

import itertools
import json
import time
from pathlib import Path

from griductive.agent.inference import LogicAgent
from griductive.agent.runner import DeductionRunner
from griductive.agent.trace import DeductionStep, DeductionTrace
from griductive.engine import GameEngine
from griductive.models import (
    BinaryClue,
    BinaryKind,
    Board,
    Cell,
    CellClassification,
    Character,
    Classification,
    ClassificationResult,
    Clue,
    ColumnRegion,
    CountClue,
    CountKind,
    EncodedKB,
    ExplicitRegion,
    FactClue,
    NeighborRegion,
    PublicState,
    Puzzle,
    Region,
    RowRegion,
    RunStatus,
    SATQuery,
    SATResult,
    SATStatus,
    SolverStats,
    Status,
    SubmitResult,
    SubmitStatus,
    VarMap,
    Verdict,
)
from griductive.puzzle_io import PuzzleLoader
from griductive.regions import RegionResolver

# ----------------------------------------------------------------------------
# Coordinates and regions


def parse(text: str) -> Cell:
    letters = "".join(ch for ch in text if ch.isalpha())
    digits = text[len(letters) :]
    col = 0
    for ch in letters:
        col = col * 26 + ord(ch) - ord("A") + 1
    return Cell(int(digits) - 1, col - 1)


def all_cells(board: Board) -> list[Cell]:
    return [Cell(r, c) for r in range(board.size) for c in range(board.size)]


class FakeRegions(RegionResolver):
    def resolve(self, region: Region, board: Board) -> tuple[Cell, ...]:
        n = board.size
        if isinstance(region, RowRegion):
            return tuple(Cell(region.row, c) for c in range(n))
        if isinstance(region, ColumnRegion):
            return tuple(Cell(r, region.col) for r in range(n))
        if isinstance(region, NeighborRegion):
            center = region.cell
            return tuple(
                Cell(r, c)
                for r in range(center.row - 1, center.row + 2)
                for c in range(center.col - 1, center.col + 2)
                if 0 <= r < n and 0 <= c < n and (r, c) != (center.row, center.col)
            )
        if isinstance(region, ExplicitRegion):
            return tuple(sorted(region.cells))
        raise ValueError(f"unknown region {region!r}")


REGIONS = FakeRegions()


def holds(clue: Clue, criminal: dict[Cell, bool], board: Board) -> bool:
    if isinstance(clue, FactClue):
        return criminal[clue.target] == (clue.status is Status.CRIMINAL)
    if isinstance(clue, BinaryClue):
        same = criminal[clue.left] == criminal[clue.right]
        return same if clue.kind is BinaryKind.SAME else not same
    if isinstance(clue, CountClue):
        count = sum(criminal[cell] for cell in REGIONS.resolve(clue.region, board))
        if clue.kind is CountKind.EXACTLY:
            return count == clue.k
        if clue.kind is CountKind.AT_LEAST:
            return count >= clue.k
        return count <= clue.k
    raise ValueError(f"unknown clue {clue!r}")


def models(
    board: Board, clues: tuple[Clue, ...], verdicts: tuple[Verdict, ...]
) -> list[dict[Cell, bool]]:
    known = {v.cell: v.status is Status.CRIMINAL for v in verdicts}
    free = [cell for cell in all_cells(board) if cell not in known]
    found = []
    for bits in itertools.product((False, True), repeat=len(free)):
        criminal = dict(known)
        criminal.update(zip(free, bits))
        if all(holds(clue, criminal, board) for clue in clues):
            found.append(criminal)
    return found


def _query(literal: int, sat: bool) -> SATQuery:
    stats = SolverStats(0, 0, 0, 0.0)
    status = SATStatus.SAT if sat else SATStatus.UNSAT
    return SATQuery((literal,) if literal else (), SATResult(status, None, stats))


# ----------------------------------------------------------------------------
# Agent, engine, runner, loader


class BruteForceAgent(LogicAgent):
    """Classifies by enumerating models of the public clues only."""

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        self.calls = 0

    def build_kb(self, state: PublicState) -> EncodedKB:
        return EncodedKB((), VarMap(tuple(all_cells(state.board))))

    def classify(self, state: PublicState) -> ClassificationResult:
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        kb = self.build_kb(state)
        found = models(state.board, state.clues, state.verdicts)
        if not found:
            return ClassificationResult(
                RunStatus.INCONSISTENT, kb, (), (_query(0, False),)
            )
        known = {v.cell for v in state.verdicts}
        ids = {cell: i + 1 for i, cell in enumerate(all_cells(state.board))}
        cells, queries = [], [_query(0, True)]
        for cell in all_cells(state.board):
            if cell in known:
                continue
            can_criminal = any(m[cell] for m in found)
            can_innocent = any(not m[cell] for m in found)
            queries += [
                _query(-ids[cell], can_innocent),
                _query(ids[cell], can_criminal),
            ]
            if not can_innocent:
                label = Classification.CRIMINAL
            elif not can_criminal:
                label = Classification.INNOCENT
            else:
                label = Classification.UNKNOWN
            cells.append(CellClassification(cell, label))
        if not cells:
            status = RunStatus.SOLVED
        elif all(c.classification is Classification.UNKNOWN for c in cells):
            status = RunStatus.STUCK
        else:
            status = RunStatus.RUNNING
        return ClassificationResult(status, kb, tuple(cells), tuple(queries))


class FakeEngine(GameEngine):
    def __init__(self, judge: BruteForceAgent | None = None) -> None:
        self.judge = judge or BruteForceAgent()
        self._puzzle: Puzzle | None = None
        self._state: PublicState | None = None

    def load(self, puzzle: Puzzle) -> PublicState:
        self._puzzle = puzzle
        return self.restart()

    def restart(self) -> PublicState:
        if self._puzzle is None:
            raise RuntimeError("no puzzle loaded")
        p = self._puzzle
        solution = {v.cell: v for v in p.solution}
        cells = sorted(p.initially_revealed)
        self._state = PublicState(
            p.board,
            tuple(solution[c] for c in cells),
            tuple(sorted((c for c in p.clues if c.owner in cells), key=_owner)),
        )
        return self._state

    def public_state(self) -> PublicState:
        if self._state is None:
            raise RuntimeError("no puzzle loaded")
        return self._state

    def submit(self, cell: Cell, status: Status) -> SubmitResult:
        state = self.public_state()
        kb = self.judge.build_kb(state)
        if any(v.cell == cell for v in state.verdicts):
            return SubmitResult(SubmitStatus.ALREADY_REVEALED, state, None, kb, ())
        analysis = self.judge.classify(state)
        if analysis.status is RunStatus.INCONSISTENT:
            return SubmitResult(
                SubmitStatus.INCONSISTENT, state, None, kb, analysis.queries
            )
        label = next(c.classification for c in analysis.cells if c.cell == cell)
        if label is Classification.UNKNOWN:
            outcome = SubmitStatus.NOT_PROVABLE
        elif label.value != status.value:
            outcome = SubmitStatus.CONTRADICTED
        else:
            outcome = SubmitStatus.ACCEPTED
        if outcome is not SubmitStatus.ACCEPTED:
            return SubmitResult(outcome, state, None, kb, analysis.queries)

        assert self._puzzle is not None
        clue = next(c for c in self._puzzle.clues if c.owner == cell)
        self._state = PublicState(
            state.board,
            tuple(sorted(state.verdicts + (Verdict(cell, status),), key=_cell)),
            tuple(sorted(state.clues + (clue,), key=_owner)),
        )
        return SubmitResult(outcome, self._state, clue, kb, analysis.queries)


class FakeRunner(DeductionRunner):
    def step(self, engine: GameEngine, agent: LogicAgent, number: int) -> DeductionStep:
        state = engine.public_state()
        analysis = agent.classify(state)
        ids = tuple(c.id for c in state.clues)
        forced = next(
            (
                c
                for c in analysis.cells
                if c.classification is not Classification.UNKNOWN
            ),
            None,
        )
        if forced is None:
            return DeductionStep(
                number, ids, analysis, None, None, state, analysis.status
            )
        verdict = Verdict(forced.cell, Status(forced.classification.value))
        result = engine.submit(verdict.cell, verdict.status)
        if result.status is not SubmitStatus.ACCEPTED:
            raise RuntimeError(f"proved verdict rejected: {result.status}")
        done = len(result.state.verdicts) == state.board.size**2
        status = RunStatus.SOLVED if done else RunStatus.RUNNING
        return DeductionStep(
            number, ids, analysis, verdict, result, result.state, status
        )

    def run(self, engine: GameEngine, agent: LogicAgent) -> DeductionTrace:
        steps, number = [], 1
        while True:
            step = self.step(engine, agent, number)
            steps.append(step)
            if step.status is not RunStatus.RUNNING:
                return DeductionTrace(tuple(steps), step.state, step.status)
            number += 1


class JsonPuzzleLoader(PuzzleLoader):
    """Minimal reader for the docs/architecture.md schema, without validation."""

    def load(self, path: Path) -> Puzzle:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        board = Board(
            data["size"],
            tuple(
                Character(parse(c["cell"]), c["name"], c["profession"])
                for c in data["characters"]
            ),
        )
        return Puzzle(
            data["id"],
            board,
            tuple(clue_from_json(c) for c in data["clues"]),
            tuple(
                Verdict(parse(cell), Status(value))
                for cell, value in data["solution"].items()
            ),
            tuple(parse(cell) for cell in data["initially_revealed"]),
        )


def region_from_json(data: dict) -> Region:
    kind = data["type"]
    if kind == "ROW":
        return RowRegion(data["row"] - 1)
    if kind == "COLUMN":
        return ColumnRegion(parse(data["column"] + "1").col)
    if kind == "NEIGHBORS":
        return NeighborRegion(parse(data["cell"]))
    return ExplicitRegion(tuple(parse(cell) for cell in data["cells"]))


def clue_from_json(data: dict) -> Clue:
    owner, kind = parse(data["owner"]), data["type"]
    if kind == "FACT":
        return FactClue(
            data["id"], owner, parse(data["target"]), Status(data["status"])
        )
    if kind in ("SAME", "DIFFERENT"):
        return BinaryClue(
            data["id"],
            owner,
            BinaryKind(kind),
            parse(data["left"]),
            parse(data["right"]),
        )
    return CountClue(
        data["id"], owner, CountKind(kind), data["k"], region_from_json(data["region"])
    )


def _cell(verdict: Verdict) -> Cell:
    return verdict.cell


def _owner(clue: Clue) -> Cell:
    return clue.owner
