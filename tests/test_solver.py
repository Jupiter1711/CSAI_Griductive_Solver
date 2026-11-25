import random
from itertools import product

import pytest

from griductive.models import Cell, SATStatus, VarMap
from griductive.solver import DPLLSolver


def var_map(n: int, aux: int = 0) -> VarMap:
    return VarMap(tuple(Cell(0, col) for col in range(n)), aux)


def solve(cnf, n, assumptions=(), aux=0):
    return DPLLSolver().solve(cnf, var_map(n, aux), assumptions)


def stats(result):
    s = result.stats
    return s.decisions, s.propagations, s.backtracks


def satisfies(model, cnf, assumptions=()) -> bool:
    values = dict(model)
    return all(any(values[abs(lit)] == (lit > 0) for lit in c) for c in cnf) and all(
        values[abs(lit)] == (lit > 0) for lit in assumptions
    )


def brute_force_sat(cnf, n, assumptions=()) -> bool:
    for bits in product((False, True), repeat=n):
        model = tuple(zip(range(1, n + 1), bits))
        if satisfies(model, cnf, assumptions):
            return True
    return False


def test_empty_cnf_without_variables_is_sat_with_empty_model():
    result = solve((), 0)
    assert result.status is SATStatus.SAT
    assert result.model == ()
    assert stats(result) == (0, 0, 0)


def test_empty_cnf_returns_every_declared_variable():
    result = solve((), 2, aux=1)
    assert result.status is SATStatus.SAT
    assert result.model == ((1, False), (2, False), (3, False))


def test_empty_clause_is_unsat():
    result = solve(((1, 2), ()), 2)
    assert result.status is SATStatus.UNSAT
    assert result.model is None


def test_unconstrained_variables_are_in_model():
    result = solve(((2,),), 3)
    assert result.model == ((1, False), (2, True), (3, False))


def test_chain_propagation_without_decisions():
    result = solve(((1,), (-1, 2), (-2, 3)), 3)
    assert result.model == ((1, True), (2, True), (3, True))
    assert stats(result) == (0, 3, 0)


def test_unit_conflict_is_unsat_without_search():
    result = solve(((1,), (-1, 2), (-2,)), 2)
    assert result.status is SATStatus.UNSAT
    assert stats(result) == (0, 2, 0)


def test_failed_branch_is_backtracked_and_flipped():
    result = solve(((1, 2), (1, -2)), 2)
    assert result.model == ((1, True), (2, False))
    assert stats(result) == (3, 1, 1)


def test_exhausted_branches_are_unsat():
    cnf = ((1, 2), (1, -2), (-1, 2), (-1, -2))
    result = solve(cnf, 2)
    assert result.status is SATStatus.UNSAT
    assert stats(result) == (2, 2, 2)


def test_branching_is_deterministic():
    cnf = ((1, 2, 3), (-1, -2), (-2, -3), (2, 3))
    first, second = solve(cnf, 3), solve(cnf, 3)
    assert first.model == second.model
    assert stats(first) == stats(second)


def test_assumptions_apply_and_do_not_leak_between_calls():
    solver = DPLLSolver()
    cnf = ((1, 2),)
    variables = var_map(2)
    forced = solver.solve(cnf, variables, (-1,))
    assert forced.model == ((1, False), (2, True))
    assert forced.stats.propagations == 1
    assert solver.solve(cnf, variables, (-1, -2)).status is SATStatus.UNSAT
    free = solver.solve(cnf, variables)
    assert free.status is SATStatus.SAT
    assert stats(free) == (1, 1, 0)


def test_contradictory_assumptions_are_unsat_not_error():
    assert solve((), 1, (1, -1)).status is SATStatus.UNSAT


def test_assumption_conflicting_with_unit_clause_is_unsat():
    assert solve(((1,),), 1, (-1,)).status is SATStatus.UNSAT


def test_input_is_not_mutated():
    cnf = ((3, 1, 2), (-1, -2), (-3,))
    snapshot = tuple(tuple(c) for c in cnf)
    solve(cnf, 3, (2,))
    assert cnf == snapshot


def test_duplicate_literals_and_tautologies_are_handled():
    result = solve(((1, 1), (2, -2), (-1, 3, 3)), 3)
    assert result.status is SATStatus.SAT
    assert satisfies(result.model, ((1,), (-1, 3)))


def test_reused_cnf_gives_same_results_and_stats_as_fresh_solver():
    cnf = ((1, 2, 3), (-1, -2), (-2, -3), (2, 3), (-3, 4))
    shared = DPLLSolver()
    for assumptions in [(), (1,), (-2,), (3,), (), (2, 3), (-4,)]:
        reused = shared.solve(cnf, var_map(4), assumptions)
        fresh = DPLLSolver().solve(cnf, var_map(4), assumptions)
        assert (reused.status, reused.model) == (fresh.status, fresh.model)
        assert stats(reused) == stats(fresh)


def test_cache_respects_declared_variable_count():
    solver = DPLLSolver()
    cnf = ((1, 2),)
    assert len(solver.solve(cnf, var_map(2)).model) == 2
    assert len(solver.solve(cnf, var_map(3)).model) == 3
    with pytest.raises(ValueError):
        solver.solve(cnf, var_map(1))


def test_mutable_clauses_are_not_cached():
    solver = DPLLSolver()
    clause = [1]
    cnf = (clause,)
    assert solver.solve(cnf, var_map(1)).model == ((1, True),)
    clause[0] = -1
    assert solver.solve(cnf, var_map(1)).model == ((1, False),)


def test_runtime_is_measured_per_call():
    result = solve(((1, 2),), 2)
    assert result.stats.runtime_s >= 0


@pytest.mark.parametrize(
    "cnf,assumptions",
    [
        (((0,),), ()),
        (((1, 3),), ()),
        (((-3,),), ()),
        (((True,),), ()),
        (((1.0,),), ()),
        (((1,),), (0,)),
        (((1,),), (5,)),
        (((1,),), (False,)),
        (([1, "2"],), ()),
        ("not a cnf", ()),
        ((1, 2), ()),
        (((1,),), 1),
    ],
)
def test_invalid_literals_raise_value_error(cnf, assumptions):
    with pytest.raises(ValueError):
        solve(cnf, 2, assumptions)


@pytest.mark.parametrize(
    "variables",
    [None, (Cell(0, 0),), VarMap((Cell(0, 0),), -1), VarMap((Cell(0, 0),), True)],
)
def test_invalid_var_map_raises_value_error(variables):
    with pytest.raises(ValueError):
        DPLLSolver().solve((), variables)


def test_matches_brute_force_on_random_cnfs():
    rng = random.Random(2026)
    solver = DPLLSolver()
    for _ in range(400):
        n = rng.randint(1, 7)
        cnf = tuple(
            tuple(
                rng.choice((1, -1)) * rng.randint(1, n)
                for _ in range(rng.randint(1, 3))
            )
            for _ in range(rng.randint(0, 3 * n))
        )
        assumptions = tuple(
            rng.choice((1, -1)) * rng.randint(1, n) for _ in range(rng.randint(0, 2))
        )
        result = solver.solve(cnf, var_map(n), assumptions)
        expected = brute_force_sat(cnf, n, assumptions)
        assert (result.status is SATStatus.SAT) == expected, (cnf, assumptions)
        if expected:
            assert [var for var, _ in result.model] == list(range(1, n + 1))
            assert satisfies(result.model, cnf, assumptions), (cnf, assumptions)
        else:
            assert result.model is None
