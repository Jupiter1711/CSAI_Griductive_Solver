"""Run the Dragon Ball GUI against brute-force stand-ins (dev preview only).

The real encoder/DPLL/engine/runner are still being written by the team, so
this script wires PygameUI to ``tests/fakes.py``. Replace the fakes with the
real classes in main.py once they exist.

    python tools/preview_gui.py                      # open the window
    python tools/preview_gui.py --delay 1.5          # simulate a slow solver
    python tools/preview_gui.py --screenshots out/   # headless PNG tour
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from griductive.models import Cell, Status  # noqa: E402
from tests.fakes import (  # noqa: E402
    BruteForceAgent,
    FakeEngine,
    FakeRegions,
    FakeRunner,
    JsonPuzzleLoader,
)

DEMO_DIR = ROOT / "tests" / "fixtures" / "gui"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--puzzle", type=Path, help="JSON puzzle to open first")
    parser.add_argument("--delay", type=float, default=0.0, help="fake agent delay (s)")
    parser.add_argument("--screenshots", type=Path, help="save a PNG tour and exit")
    parser.add_argument(
        "--size", default="2880x1840", help="screenshot size, e.g. 1440x920"
    )
    args = parser.parse_args()

    if args.screenshots:
        os.environ["SDL_VIDEODRIVER"] = "dummy"

    from griductive.gui.app import GriductiveWindow, PygameUI
    from griductive.gui.controller import GameController

    agent = BruteForceAgent(args.delay)
    engine = FakeEngine(BruteForceAgent(args.delay))
    parts = (engine, agent, FakeRunner(), JsonPuzzleLoader(), FakeRegions())
    puzzle_dirs = (DEMO_DIR, ROOT / "puzzles")

    if not args.screenshots:
        PygameUI(puzzle_dirs, args.puzzle).run(*parts)
        return

    out = args.screenshots
    out.mkdir(parents=True, exist_ok=True)
    ctl = GameController(*parts, step_delay=0.0)
    width, height = map(int, args.size.split("x"))
    window = GriductiveWindow(ctl, puzzle_dirs, window_size=(width, height))

    def shot(name: str, settle: bool = True) -> None:
        if settle:
            ctl.reveal_times.clear()  # skip flip animation in stills
        window.save(out / f"{name}.png")
        print("saved", out / f"{name}.png")

    window.open_picker()
    shot("00-picker")
    window.picker_open = False

    puzzle = args.puzzle or DEMO_DIR / "4x4-tenkaichi-1.json"
    ctl.load(puzzle)
    ctl.wait()
    shot("01-loaded")

    ctl.request_hint()
    ctl.wait()
    shot("02-hint")

    hint_cell = ctl.hint.cell if ctl.hint else Cell(0, 0)
    wrong = (
        Status.INNOCENT
        if ctl.hint and ctl.hint.classification.value == "CRIMINAL"
        else Status.CRIMINAL
    )
    ctl.select_cell(hint_cell)
    ctl.submit(wrong)
    ctl.wait()
    shot("03-contradicted")

    unknown = next(
        (
            c.cell
            for c in agent.classify(ctl.state).cells
            if c.classification.value == "UNKNOWN"
        ),
        None,
    )
    if unknown is not None:
        ctl.select_cell(unknown)
        ctl.submit(Status.CRIMINAL)
        ctl.wait()
        shot("04-not-provable")

    ctl.select_cell(hint_cell)
    ctl.submit(Status(ctl.hint.classification.value) if ctl.hint else Status.CRIMINAL)
    ctl.wait()
    shot("05-accepted")

    ctl.toggle_auto()
    ctl.wait(120)
    shot("06-solved")


if __name__ == "__main__":
    main()
