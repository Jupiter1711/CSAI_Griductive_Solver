import argparse
from pathlib import Path

from griductive.agent.inference import GriductiveLogicAgent
from griductive.agent.runner import GriductiveRunner
from griductive.encoder import BasicCNFEncoder
from griductive.engine import GridGameEngine
from griductive.evaluator import DirectClueEvaluator
from griductive.gui.app import PygameUI
from griductive.puzzle_io import JsonPuzzleLoader
from griductive.regions import GridRegionResolver
from griductive.solver import DPLLSolver
from griductive.validation import SATPuzzleValidator

PUZZLE_DIR = Path(__file__).resolve().parent / "puzzles"


def new_agent() -> GriductiveLogicAgent:
    return GriductiveLogicAgent(BasicCNFEncoder(), DPLLSolver())


def main() -> None:
    parser = argparse.ArgumentParser(description="Play Griductive.")
    parser.add_argument("--puzzle", type=Path, help="JSON puzzle to open first")
    args = parser.parse_args()

    validator = SATPuzzleValidator(
        BasicCNFEncoder(), DPLLSolver(), DirectClueEvaluator()
    )
    engine = GridGameEngine(validator, judge=new_agent())
    PygameUI((PUZZLE_DIR,), args.puzzle).run(
        engine,
        new_agent(),
        GriductiveRunner(),
        JsonPuzzleLoader(),
        GridRegionResolver(),
    )


if __name__ == "__main__":
    main()
