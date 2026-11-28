import pytest

from griductive.models import RunStatus
from griductive.puzzle_io import JsonPuzzleLoader
from main import PUZZLE_DIR, new_system


@pytest.mark.parametrize(
    "filename",
    [f"{size}x{size}-{number:02}.json" for size in (3, 4, 5) for number in (1, 2, 3)],
)
def test_official_puzzle_solves_from_initial_reveals(filename):
    puzzle = JsonPuzzleLoader().load(PUZZLE_DIR / filename)
    system = new_system()
    system.engine.load(puzzle)

    trace = system.runner.run(system.engine, system.agent)

    assert trace.status is RunStatus.SOLVED
    assert set(trace.final_state.verdicts) == set(puzzle.solution)
