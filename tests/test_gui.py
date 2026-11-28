"""GUI tests: wording, highlighting, controller flow and a headless window smoke."""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from griductive.agent.inference import GriductiveLogicAgent
from griductive.agent.runner import GriductiveRunner
from griductive.encoder import BasicCNFEncoder
from griductive.engine import GridGameEngine
from griductive.evaluator import DirectClueEvaluator
from griductive.gui.controller import GameController, MessageKind
from griductive.gui.highlight import clue_focus, related_clue
from griductive.gui.text import cell_label, describe_clue
from griductive.models import (
    BinaryClue,
    BinaryKind,
    Board,
    Cell,
    Character,
    Classification,
    ColumnRegion,
    CountClue,
    CountKind,
    ExplicitRegion,
    FactClue,
    IntersectionClue,
    NeighborRegion,
    ParityClue,
    ParityKind,
    PublicState,
    Puzzle,
    RowRegion,
    RunStatus,
    Status,
)
from griductive.puzzle_io import JsonPuzzleLoader
from griductive.regions import GridRegionResolver
from griductive.solver import DPLLSolver
from griductive.validation import SATPuzzleValidator

ROOT = Path(__file__).resolve().parents[1]
PUZZLES = ROOT / "puzzles"
PUZZLE_3X3 = PUZZLES / "3x3-01.json"
REGIONS = GridRegionResolver()
NAMES = ["Bulma", "Chiaotzu", "Gohan", "Goku", "Krillin", "Piccolo", "Roshi"]
NAMES += ["Vegeta", "Yamcha"]
BOARD = Board(
    3, tuple(Character(Cell(i // 3, i % 3), n, "Fighter") for i, n in enumerate(NAMES))
)


class SlowAgent(GriductiveLogicAgent):
    def __init__(self, delay: float = 0.0) -> None:
        super().__init__(BasicCNFEncoder(), DPLLSolver())
        self.delay = delay

    def classify(self, state: PublicState):
        time.sleep(self.delay)
        return super().classify(state)


def make_controller(delay: float = 0.0) -> GameController:
    validator = SATPuzzleValidator(
        BasicCNFEncoder(), DPLLSolver(), DirectClueEvaluator()
    )
    engine = GridGameEngine(validator, SlowAgent())
    return GameController(
        engine,
        SlowAgent(delay),
        GriductiveRunner(),
        JsonPuzzleLoader(),
        REGIONS,
        step_delay=0.0,
    )


def loaded() -> GameController:
    ctl = make_controller()
    assert ctl.load(PUZZLE_3X3)
    ctl.wait()
    return ctl


def forced_cells(ctl: GameController) -> dict[Cell, Classification]:
    analysis = SlowAgent().classify(ctl.state)
    return {c.cell: c.classification for c in analysis.cells}


# --------------------------------------------------------------------------
# Import boundary


@pytest.mark.parametrize(
    "module",
    ["griductive.gui", "griductive.gui.controller", "griductive.gui.text"],
)
def test_pure_gui_modules_do_not_import_pygame(module):
    code = f"import sys, {module}; assert 'pygame' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True, cwd=ROOT)


# --------------------------------------------------------------------------
# Wording


def test_cell_label_uses_column_letter_then_row():
    assert cell_label(Cell(1, 2)) == "C2"
    assert cell_label(Cell(0, 26)) == "AA1"


@pytest.mark.parametrize(
    "clue,text",
    [
        (
            FactClue("f", Cell(0, 0), Cell(1, 1), Status.CRIMINAL),
            "Krillin is a criminal.",
        ),
        (
            FactClue("f", Cell(0, 0), Cell(1, 1), Status.INNOCENT),
            "Krillin is innocent.",
        ),
        (
            BinaryClue("s", Cell(0, 0), BinaryKind.SAME, Cell(0, 1), Cell(2, 2)),
            "Chiaotzu and Yamcha are both criminals or both innocent.",
        ),
        (
            BinaryClue("d", Cell(0, 0), BinaryKind.DIFFERENT, Cell(0, 1), Cell(2, 2)),
            "Exactly one of Chiaotzu and Yamcha is a criminal.",
        ),
        (
            CountClue("c", Cell(0, 0), CountKind.EXACTLY, 0, RowRegion(1)),
            "There are no criminals in row 2.",
        ),
        (
            CountClue("c", Cell(0, 0), CountKind.EXACTLY, 1, ColumnRegion(2)),
            "There is exactly 1 criminal in column C.",
        ),
        (
            CountClue(
                "c", Cell(0, 0), CountKind.AT_LEAST, 2, NeighborRegion(Cell(1, 1))
            ),
            "There are at least 2 criminals among Krillin's neighbors.",
        ),
        (
            CountClue(
                "c",
                Cell(0, 0),
                CountKind.AT_MOST,
                1,
                ExplicitRegion((Cell(0, 0), Cell(2, 1), Cell(1, 2))),
            ),
            "There is at most 1 criminal among A1, B3 and C2.",
        ),
        (
            ParityClue("p", Cell(0, 0), ParityKind.ODD, RowRegion(0)),
            "There is an odd number of criminals in row 1.",
        ),
        (
            ParityClue("p", Cell(0, 0), ParityKind.EVEN, NeighborRegion(Cell(1, 1))),
            "There is an even number of criminals among Krillin's neighbors.",
        ),
        (
            IntersectionClue("i", Cell(0, 0), 1, (RowRegion(0), ColumnRegion(1))),
            "Exactly 1 person who is both in row 1 and in column B is a criminal.",
        ),
        (
            IntersectionClue("i", Cell(0, 0), 0, (RowRegion(2), ColumnRegion(0))),
            "No one who is both in row 3 and in column A is a criminal.",
        ),
        (
            IntersectionClue(
                "i",
                Cell(0, 0),
                2,
                (RowRegion(0), ColumnRegion(1), NeighborRegion(Cell(1, 1))),
            ),
            "Exactly 2 people who are in row 1, in column B and among Krillin's "
            "neighbors are criminals.",
        ),
    ],
)
def test_describe_clue(clue, text):
    assert describe_clue(clue, BOARD) == text


# --------------------------------------------------------------------------
# Highlighting


def test_focus_counts_region_and_marks_neighbor_center_as_anchor():
    clue = CountClue("c", Cell(0, 0), CountKind.EXACTLY, 1, NeighborRegion(Cell(0, 0)))
    focus = clue_focus(clue, BOARD, REGIONS)
    assert focus.counted == (Cell(0, 1), Cell(1, 0), Cell(1, 1))
    assert focus.anchors == (Cell(0, 0),)


def test_focus_for_fact_and_binary_clues():
    regions = REGIONS
    fact = FactClue("f", Cell(0, 0), Cell(2, 2), Status.CRIMINAL)
    same = BinaryClue("s", Cell(0, 0), BinaryKind.SAME, Cell(2, 0), Cell(0, 2))
    assert clue_focus(fact, BOARD, regions).counted == (Cell(2, 2),)
    assert clue_focus(same, BOARD, regions).counted == (Cell(0, 2), Cell(2, 0))


def test_focus_for_parity_and_intersection_clues():
    parity = ParityClue("p", Cell(0, 0), ParityKind.EVEN, NeighborRegion(Cell(0, 0)))
    focus = clue_focus(parity, BOARD, REGIONS)
    assert focus.counted == (Cell(0, 1), Cell(1, 0), Cell(1, 1))
    assert focus.anchors == (Cell(0, 0),)

    both = IntersectionClue("i", Cell(0, 0), 1, (RowRegion(1), ColumnRegion(2)))
    assert clue_focus(both, BOARD, REGIONS).counted == (Cell(1, 2),)


def test_related_clue_is_first_revealed_clue_mentioning_cell():
    row = CountClue("r", Cell(0, 0), CountKind.EXACTLY, 1, RowRegion(2))
    col = CountClue("c", Cell(0, 1), CountKind.EXACTLY, 1, ColumnRegion(0))
    assert related_clue(Cell(2, 0), (row, col), BOARD, REGIONS) is row
    assert related_clue(Cell(1, 0), (row, col), BOARD, REGIONS) is col
    assert related_clue(Cell(1, 1), (row, col), BOARD, REGIONS) is None


# --------------------------------------------------------------------------
# Controller flow


def test_load_shows_only_initial_public_cards():
    ctl = loaded()
    assert ctl.puzzle_name == PUZZLE_3X3.stem
    assert len(ctl.state.clues) == 1
    owner = ctl.state.clues[0].owner
    hidden = [c.cell for c in ctl.state.board.characters if c.cell != owner]
    assert all(ctl.clue_of_owner(cell) is None for cell in hidden)
    assert not any(isinstance(value, Puzzle) for value in vars(ctl).values())


def test_hint_points_at_forced_cell_without_revealing_it():
    ctl = loaded()
    before = ctl.engine.public_state()
    assert ctl.request_hint()
    ctl.wait()
    assert ctl.message.kind is MessageKind.HINT
    assert ctl.hint.cell is not None
    assert forced_cells(ctl)[ctl.hint.cell] is not Classification.UNKNOWN
    assert ctl.engine.public_state() == before
    assert ctl.hint.clue_id in {clue.id for clue in ctl.state.clues}


def test_contradicted_and_not_provable_keep_state():
    ctl = loaded()
    labels = forced_cells(ctl)
    forced = next(c for c, k in labels.items() if k is not Classification.UNKNOWN)
    opposite = (
        Status.INNOCENT
        if labels[forced] is Classification.CRIMINAL
        else Status.CRIMINAL
    )
    state = ctl.state

    ctl.select_cell(forced)
    ctl.submit(opposite)
    ctl.wait()
    assert ctl.message.kind is MessageKind.CONTRADICTED
    assert ctl.state is state

    unknown = next(c for c, k in labels.items() if k is Classification.UNKNOWN)
    ctl.select_cell(unknown)
    ctl.submit(Status.CRIMINAL)
    ctl.wait()
    assert ctl.message.kind is MessageKind.NOT_PROVABLE
    assert ctl.state is state
    assert ctl.clue_of_owner(unknown) is None


def test_accepted_verdict_flips_card_and_selects_new_clue():
    ctl = loaded()
    labels = forced_cells(ctl)
    cell = next(c for c, k in labels.items() if k is not Classification.UNKNOWN)
    ctl.select_cell(cell)
    ctl.submit(Status(labels[cell].value))
    ctl.wait()
    assert ctl.message.kind is MessageKind.ACCEPTED
    assert ctl.verdict_of(cell) is Status(labels[cell].value)
    clue = ctl.clue_of_owner(cell)
    assert clue is not None and ctl.selected_clue_id == clue.id
    assert cell in ctl.reveal_times
    assert ctl.focus() is not None


def test_submit_on_known_card_is_refused_locally():
    ctl = loaded()
    known = ctl.state.verdicts[0].cell
    ctl.select_cell(known)
    assert not ctl.submit(Status.CRIMINAL)
    assert ctl.message.kind is MessageKind.ALREADY_REVEALED
    assert not ctl.busy


def test_auto_solve_reaches_solved_and_restart_resets():
    ctl = loaded()
    assert ctl.toggle_auto()
    ctl.wait(60)
    assert ctl.solved
    assert ctl.run_status is RunStatus.SOLVED
    assert ctl.message.kind is MessageKind.SOLVED
    assert any(line.startswith("Step") for line in ctl.log)
    assert ctl.info.sat_calls > 0

    assert ctl.restart()
    ctl.wait()
    assert len(ctl.state.verdicts) == 1
    assert ctl.info.sat_calls == 0


def test_stop_auto_solve_between_steps():
    ctl = loaded()
    ctl.step_delay = 0.5
    ctl.toggle_auto()
    while not ctl.log[-1].startswith("Step"):
        ctl.poll()
    assert ctl.toggle_auto()  # request stop
    ctl.wait(10)
    assert not ctl.auto_running
    assert not ctl.solved
    assert ctl.message.kind is MessageKind.INFO


def test_only_one_job_at_a_time():
    ctl = make_controller(delay=0.3)
    ctl.load(PUZZLE_3X3)
    ctl.wait()
    assert ctl.request_hint()
    assert ctl.busy
    assert not ctl.restart()
    assert not ctl.toggle_auto()
    ctl.wait()
    assert not ctl.busy


def test_job_errors_become_messages():
    ctl = make_controller()
    ctl.load(ROOT / "missing.json")
    ctl.wait()
    assert ctl.message.kind is MessageKind.ERROR
    assert "FileNotFoundError" in ctl.message.text
    assert ctl.state is None


def test_stale_hint_is_dropped_after_state_changes():
    ctl = loaded()
    gate = threading.Event()
    real = ctl.agent.classify

    def slow(state: PublicState):
        gate.wait(5)
        return real(state)

    ctl.agent.classify = slow
    ctl.request_hint()
    ctl.state = PublicState(ctl.state.board, ctl.state.verdicts, ctl.state.clues)
    gate.set()
    ctl.wait()
    assert ctl.hint is None


# --------------------------------------------------------------------------
# Window smoke test (headless)


@pytest.fixture
def window():
    pytest.importorskip("pygame")
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    from griductive.gui.app import GriductiveWindow

    ctl = loaded()
    win = GriductiveWindow(ctl, (PUZZLES,))
    yield win
    win.close()


def test_window_renders_and_clicks_select(window):
    ctl = window.ctl
    window.frame()
    hidden = next(
        c.cell for c in ctl.state.board.characters if not ctl.is_face_up(c.cell)
    )
    window.click(window.card_rect(hidden).center)
    assert ctl.selected_cell == hidden

    clue = ctl.state.clues[0]
    window.frame()
    window.click(window.hits[f"clue:{clue.id}"].center)
    assert ctl.selected_clue_id == clue.id
    window.frame()


@pytest.mark.parametrize("preloaded", [False, True])
def test_mouse_click_in_picker_loads_puzzle(preloaded):
    pygame = pytest.importorskip("pygame")
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    from griductive.gui.app import GriductiveWindow

    ctl = loaded() if preloaded else make_controller()
    window = GriductiveWindow(ctl, (PUZZLES,))
    try:
        window.open_picker()
        window.frame()
        target = next(p for p in window.picker_files if p.stem == "4x4-01")
        row = window.hits[f"pick:{window.picker_files.index(target)}"]
        pos = window._painter.point(*row.center)
        window.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
        assert not window.picker_open
        ctl.wait()
        assert ctl.puzzle_name == "4x4-01"
        assert ctl.state.board.size == 4
    finally:
        window.close()


def test_window_picker_reaches_every_puzzle(window):
    window.open_picker()
    window.frame()
    last = len(window.picker_files) - 1
    assert last >= 8
    for _ in range(last):
        window._scroll_picker(1)
    window.frame()
    assert f"pick:{last}" in window.hits


def test_rejection_feedback_is_tracked():
    ctl = loaded()
    labels = forced_cells(ctl)
    unknown = next(c for c, k in labels.items() if k is Classification.UNKNOWN)
    ctl.select_cell(unknown)
    ctl.submit(Status.INNOCENT)
    ctl.wait()
    assert ctl.rejection is not None and ctl.rejection[0] == unknown


def test_portraits_fall_back_to_monogram_for_unknown_names(window):
    from griductive.gui.avatar import avatar, initials, portrait_path

    assert portrait_path("Goku") is not None
    assert portrait_path("Master Roshi") == portrait_path("Roshi")
    assert portrait_path("Goku", 100).parent.name == "128"  # smallest >= wanted
    assert portrait_path("Nobody Atall") is None
    assert initials("Nobody Atall") == "NA"
    assert avatar(window.theme, "Nobody Atall", 64).get_size() == (64, 64)


def test_log_is_closed_by_default_and_toggles(window):
    window.frame()
    assert not window.log_open
    window.click(window.hits["log"].center)
    assert window.log_open


def test_clicking_a_card_dismisses_old_feedback(window):
    ctl = window.ctl
    labels = forced_cells(ctl)
    unknown = next(c for c, k in labels.items() if k is Classification.UNKNOWN)
    ctl.select_cell(unknown)
    ctl.submit(Status.CRIMINAL)
    ctl.wait()
    assert window._feedback() is not None
    window.frame()
    other = next(c for c in labels if c != unknown)
    window.click(window.card_rect(other).center)
    assert window._feedback() is None


def test_tab_focus_cycles_buttons_and_enter_activates(window):
    import pygame

    window.frame()
    window.key(pygame.K_TAB)
    assert window.focus_visible and window.focus_key == "load"
    window.key(pygame.K_RETURN)
    assert window.picker_open


def test_text_wrap_avoids_single_short_orphan(window):
    p = window.painter()
    text = "There is at least 1 criminal in row 1."
    width = p.measure("There is at least 1 criminal in row", 15)
    lines = p.wrap(text, 15, width)
    assert lines[-1] != "1." and len(lines[-1].split()) >= 2


def test_small_mono_labels_use_medium_weight(window):
    p = window.painter()
    assert p._role("mono", 11) == "mono_medium"
    assert p._role("mono", 14) == "mono"
