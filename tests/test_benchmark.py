import csv
import multiprocessing
import time
from dataclasses import replace
from pathlib import Path

import pytest

from griductive.benchmark import BenchmarkOutcome, GriductiveBenchmarkRunner
from griductive.models import RunStatus
from griductive.puzzle_io import JsonPuzzleLoader
from main import new_system


def puzzle():
    return JsonPuzzleLoader().load(Path(__file__).parents[1] / "puzzles/3x3-01.json")


def test_suite_records_agent_and_judge_queries_and_preserves_failures(tmp_path):
    valid = puzzle()
    invalid = replace(valid, id="invalid", solution=())
    stuck = replace(valid, id="stuck", initially_revealed=())
    runner = GriductiveBenchmarkRunner()
    results = runner.run_suite((invalid, valid, stuck), "DPLL", new_system, 10)
    error, solved, stalled = results
    assert error.outcome is BenchmarkOutcome.ERROR
    assert error.error and error.metrics is None and error.runtime_s == 0
    assert solved.terminal_status is RunStatus.SOLVED
    assert solved.outcome is BenchmarkOutcome.COMPLETED
    assert set(solved.trace.final_state.verdicts) == set(valid.solution)
    metrics = solved.metrics
    # 8 hidden cells down to 1; both agent and judge ask 1 + 2*n queries.
    assert metrics.sat_calls == 2 * sum(1 + 2 * n for n in range(1, 9))
    assert metrics.primary_variables == 9 and metrics.deduction_steps == 8
    queries = [
        q
        for step in solved.trace.steps
        for record in (step.analysis, step.submission)
        for q in record.queries
    ]
    for name in ("decisions", "propagations", "backtracks"):
        assert getattr(metrics, name) == sum(
            getattr(q.result.stats, name) for q in queries
        )
    kbs = [step.analysis.kb for step in solved.trace.steps]
    assert metrics.peak_clauses == max(len(kb.cnf) for kb in kbs)
    assert metrics.peak_auxiliary_variables == max(
        kb.variables.auxiliary_count for kb in kbs
    )
    assert stalled.outcome is BenchmarkOutcome.COMPLETED
    assert stalled.terminal_status is RunStatus.STUCK
    assert stalled.metrics.deduction_steps == 0 and stalled.metrics.sat_calls == 19

    path = tmp_path / "results.csv"
    runner.export(results, path)
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [row["puzzle_id"] for row in rows] == [invalid.id, valid.id, stuck.id]
    assert rows[0]["sat_calls"] == "" and rows[0]["error"]
    assert rows[1]["sat_calls"] == str(metrics.sat_calls)
    assert rows[2]["terminal_status"] == "STUCK"
    with pytest.raises(FileExistsError):
        runner.export((), path)


class BlockingRunner:
    def run(self, engine, agent):
        time.sleep(60)


def blocking_system():
    return replace(new_system(), runner=BlockingRunner())


def test_timeout_stops_worker_before_returning():
    result = GriductiveBenchmarkRunner().run_case(puzzle(), "slow", blocking_system, 1)
    assert result.outcome is BenchmarkOutcome.TIMEOUT
    assert "deduction" in result.error
    assert result.metrics is None and result.terminal_status is None
    assert result.runtime_s > 0
    assert not multiprocessing.active_children()


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_timeout_even_for_empty_suite(timeout):
    with pytest.raises(ValueError):
        GriductiveBenchmarkRunner().run_suite((), "DPLL", new_system, timeout)
