"""Benchmark contracts. Owner: unassigned."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from griductive.agent.inference import LogicAgent
from griductive.agent.runner import DeductionRunner
from griductive.agent.trace import DeductionTrace
from griductive.engine import GameEngine
from griductive.models import Puzzle, RunStatus


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
