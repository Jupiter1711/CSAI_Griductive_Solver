import argparse
from pathlib import Path

from griductive.agent.inference import GriductiveLogicAgent
from griductive.agent.runner import GriductiveRunner
from griductive.benchmark import (
    BenchmarkOutcome,
    BenchmarkResult,
    BenchmarkSystem,
    GriductiveBenchmarkRunner,
)
from griductive.encoder import BasicCNFEncoder
from griductive.engine import GridGameEngine
from griductive.evaluator import DirectClueEvaluator
from griductive.puzzle_io import JsonPuzzleLoader
from griductive.regions import GridRegionResolver
from griductive.solver import DPLLSolver
from griductive.validation import SATPuzzleValidator

PUZZLE_DIR = Path(__file__).resolve().parent / "puzzles"


def new_agent() -> GriductiveLogicAgent:
    return GriductiveLogicAgent(BasicCNFEncoder(), DPLLSolver())


def new_system() -> BenchmarkSystem:
    validator = SATPuzzleValidator(
        BasicCNFEncoder(), DPLLSolver(), DirectClueEvaluator()
    )
    engine = GridGameEngine(validator, judge=new_agent())
    return BenchmarkSystem(engine, new_agent(), GriductiveRunner())


def main() -> None:
    parser = argparse.ArgumentParser(description="Play or benchmark Griductive.")
    parser.add_argument("--puzzle", type=Path, help="open or benchmark one JSON puzzle")
    parser.add_argument(
        "--benchmark",
        type=Path,
        metavar="CSV",
        help="write benchmark results to a new CSV",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30,
        help="benchmark time limit in seconds (default 30)",
    )
    args = parser.parse_args()

    if args.benchmark is not None:
        if not 0 < args.timeout < float("inf"):
            parser.error("--timeout must be positive and finite")
        paths = [args.puzzle] if args.puzzle else sorted(PUZZLE_DIR.glob("*.json"))
        if not paths:
            parser.error(f"no JSON puzzles found in {PUZZLE_DIR}")
        runner = GriductiveBenchmarkRunner()
        results = []
        for path in paths:
            try:
                puzzle = JsonPuzzleLoader().load(path)
            except (OSError, ValueError) as exc:
                result = BenchmarkResult(
                    path.stem,
                    "DPLL",
                    BenchmarkOutcome.ERROR,
                    None,
                    None,
                    0.0,
                    None,
                    str(exc),
                )
            else:
                result = runner.run_case(puzzle, "DPLL", new_system, args.timeout)
            results.append(result)
            label = (
                result.terminal_status.value
                if result.terminal_status
                else result.outcome.value
            )
            print(f"{path.name}: {label} ({result.runtime_s:.4f} s)")
        try:
            runner.export(tuple(results), args.benchmark)
        except OSError as exc:
            parser.error(str(exc))
        if any(result.outcome is not BenchmarkOutcome.COMPLETED for result in results):
            raise SystemExit(1)
        return

    from griductive.gui.app import PygameUI

    system = new_system()
    PygameUI((PUZZLE_DIR,), args.puzzle).run(
        system.engine,
        system.agent,
        system.runner,
        JsonPuzzleLoader(),
        GridRegionResolver(),
    )


if __name__ == "__main__":
    main()
