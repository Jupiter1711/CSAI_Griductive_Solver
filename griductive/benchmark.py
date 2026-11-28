"""Measure deduction on an isolated, freshly loaded game for each puzzle."""

import csv
import math
import multiprocessing
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from enum import Enum
from multiprocessing.connection import Connection
from pathlib import Path

from griductive.agent.inference import LogicAgent
from griductive.agent.runner import DeductionRunner
from griductive.agent.trace import DeductionTrace
from griductive.engine import GameEngine
from griductive.models import Puzzle, RunStatus, SubmitStatus


class BenchmarkOutcome(str, Enum):
    COMPLETED = "COMPLETED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


@dataclass(frozen=True)
class BenchmarkMetrics:
    primary_variables: int
    peak_auxiliary_variables: int
    peak_clauses: int
    sat_calls: int
    decisions: int
    propagations: int
    backtracks: int
    deduction_steps: int


@dataclass(frozen=True)
class BenchmarkResult:
    puzzle_id: str
    variant: str
    outcome: BenchmarkOutcome
    terminal_status: RunStatus | None
    metrics: BenchmarkMetrics | None
    runtime_s: float
    trace: DeductionTrace | None
    error: str | None


@dataclass(frozen=True)
class BenchmarkSystem:
    """One fresh set of collaborators, wired by the caller for one case."""

    engine: GameEngine
    agent: LogicAgent
    runner: DeductionRunner


class BenchmarkRunner(ABC):
    @abstractmethod
    def run_case(
        self,
        puzzle: Puzzle,
        variant: str,
        create_system: Callable[[], BenchmarkSystem],
        timeout_s: float,
    ) -> BenchmarkResult:
        """Run one case with fresh collaborators and an enforced positive timeout.

        Preserve errors/timeouts as results, never UNSAT or fabricated zero
        metrics. Validate/load before timing deduction. Measure wall-clock
        deduction time, including judge calls; exclude setup/uniqueness checks.
        Enforce timeout around blocking work with a cancellable isolated worker
        (checking time only after run returns is insufficient). Factory must be
        a top-level picklable callable for process-based implementations.
        """
        raise NotImplementedError

    @abstractmethod
    def run_suite(
        self,
        puzzles: tuple[Puzzle, ...],
        variant: str,
        create_system: Callable[[], BenchmarkSystem],
        timeout_s: float,
    ) -> tuple[BenchmarkResult, ...]:
        """Return one result per input case in order, including errors/timeouts.

        Use the identical puzzle tuple for each compared variant. Each case
        gets a fresh system; invalid timeout raises ValueError.
        """
        raise NotImplementedError

    @abstractmethod
    def export(self, results: tuple[BenchmarkResult, ...], path: Path) -> None:
        """Write UTF-8 CSV summary, one row per result, including failures.

        Flatten metrics; unknown values are blank, not zero. Include variant,
        outcome, terminal status, runtime and error. Trace stays in memory.
        Refuse existing destinations with FileExistsError; propagate I/O errors.
        """
        raise NotImplementedError


def _metrics(trace: DeductionTrace) -> BenchmarkMetrics:
    peak_aux = peak_clauses = calls = decisions = propagations = backtracks = steps = 0
    for step in trace.steps:
        records = [step.analysis]
        if step.submission is not None:
            records.append(step.submission)
            if step.submission.status is SubmitStatus.ACCEPTED:
                steps += 1
        for record in records:
            peak_aux = max(peak_aux, record.kb.variables.auxiliary_count)
            peak_clauses = max(peak_clauses, len(record.kb.cnf))
            calls += len(record.queries)
            for query in record.queries:
                stats = query.result.stats
                decisions += stats.decisions
                propagations += stats.propagations
                backtracks += stats.backtracks
    return BenchmarkMetrics(
        trace.final_state.board.size**2,
        peak_aux,
        peak_clauses,
        calls,
        decisions,
        propagations,
        backtracks,
        steps,
    )


def _run_worker(
    pipe: Connection, puzzle: Puzzle, create_system: Callable[[], BenchmarkSystem]
) -> None:
    with pipe:
        try:
            system = create_system()
            system.engine.load(puzzle)
        except Exception as exc:
            pipe.send(f"{type(exc).__name__}: {exc}")
            return

        pipe.send(time.perf_counter())
        start = time.perf_counter()
        try:
            result = system.runner.run(system.engine, system.agent)
        except Exception as exc:
            result = f"{type(exc).__name__}: {exc}"
        # Notify the parent before serializing the potentially large trace.
        pipe.send(time.perf_counter() - start)
        pipe.send(result)


def _check_timeout(timeout_s: float) -> None:
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("timeout_s must be positive and finite")


class GriductiveBenchmarkRunner(BenchmarkRunner):
    def run_case(
        self,
        puzzle: Puzzle,
        variant: str,
        create_system: Callable[[], BenchmarkSystem],
        timeout_s: float,
    ) -> BenchmarkResult:
        _check_timeout(timeout_s)
        ctx = multiprocessing.get_context("spawn")
        reader, writer = ctx.Pipe(duplex=False)
        worker = ctx.Process(target=_run_worker, args=(writer, puzzle, create_system))
        started = None
        elapsed = None
        outcome = BenchmarkOutcome.ERROR
        try:
            worker.start()
            writer.close()
            if not reader.poll(timeout_s):
                raise TimeoutError("setup exceeded the time limit")
            ready = reader.recv()
            if isinstance(ready, str):
                raise RuntimeError(ready)
            started = ready
            if not reader.poll(max(0.0, started + timeout_s - time.perf_counter())):
                raise TimeoutError("deduction exceeded the time limit")
            elapsed = reader.recv()
            if elapsed > timeout_s:
                raise TimeoutError("deduction exceeded the time limit")
            trace = reader.recv()
            if isinstance(trace, str):
                raise RuntimeError(trace)
            return BenchmarkResult(
                puzzle.id,
                variant,
                BenchmarkOutcome.COMPLETED,
                trace.status,
                _metrics(trace),
                elapsed,
                trace,
                None,
            )
        except TimeoutError as exc:
            outcome = BenchmarkOutcome.TIMEOUT
            error = str(exc)
        except EOFError:
            error = "benchmark worker exited without returning its result"
        except Exception as exc:
            error = str(exc) or type(exc).__name__
        finally:
            reader.close()
            writer.close()
            if worker.pid is not None:
                if elapsed is None and started is not None:
                    elapsed = time.perf_counter() - started
                if elapsed is not None and outcome is not BenchmarkOutcome.TIMEOUT:
                    worker.join(timeout=0.1)
                if worker.is_alive():
                    worker.kill()
                worker.join()
            worker.close()
        return BenchmarkResult(
            puzzle.id, variant, outcome, None, None, elapsed or 0.0, None, error
        )

    def run_suite(
        self,
        puzzles: tuple[Puzzle, ...],
        variant: str,
        create_system: Callable[[], BenchmarkSystem],
        timeout_s: float,
    ) -> tuple[BenchmarkResult, ...]:
        _check_timeout(timeout_s)
        return tuple(
            self.run_case(p, variant, create_system, timeout_s) for p in puzzles
        )

    def export(self, results: tuple[BenchmarkResult, ...], path: Path) -> None:
        columns = [
            "puzzle_id",
            "variant",
            "outcome",
            "terminal_status",
            "runtime_s",
            "error",
            *(field.name for field in fields(BenchmarkMetrics)),
        ]
        with path.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            for result in results:
                writer.writerow(
                    {
                        "puzzle_id": result.puzzle_id,
                        "variant": result.variant,
                        "outcome": result.outcome.value,
                        "terminal_status": (
                            result.terminal_status.value
                            if result.terminal_status
                            else None
                        ),
                        "runtime_s": result.runtime_s,
                        "error": result.error,
                        **(asdict(result.metrics) if result.metrics else {}),
                    }
                )
