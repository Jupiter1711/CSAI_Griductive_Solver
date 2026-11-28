import pytest

from griductive.models import RunStatus
from griductive.puzzle_io import JsonPuzzleLoader
from main import PUZZLE_DIR, new_system


@pytest.mark.parametrize(
    "path", sorted(PUZZLE_DIR.glob("*.json")), ids=lambda path: path.stem
)
def test_official_puzzle_solves_from_initial_reveals(path):
    puzzle = JsonPuzzleLoader().load(path)
    system = new_system()
    system.engine.load(puzzle)

    trace = system.runner.run(system.engine, system.agent)

    assert trace.status is RunStatus.SOLVED
    assert set(trace.final_state.verdicts) == set(puzzle.solution)
