"""Exhaustive semantic comparison for the team's concrete encoder and solver."""

from itertools import product

import pytest

from griductive.evaluator import DirectClueEvaluator
from griductive.models import (
    BinaryClue,
    BinaryKind,
    Board,
    Cell,
    Character,
    CountClue,
    CountKind,
    FactClue,
    RowRegion,
    SATStatus,
    Status,
)


@pytest.fixture
def logic_backend():
    # Replace this fixture with the team's concrete constructors at integration.
    pytest.skip("Waiting for concrete CNFEncoder and SATSolver on this branch")


def test_encoded_clue_matches_direct_semantics(logic_backend):
    encoder, solver = logic_backend
    evaluator = DirectClueEvaluator()
    cells = tuple(Cell(r, c) for r in range(2) for c in range(2))
    board = Board(2, tuple(Character(c, n, "") for c, n in zip(cells, "ABCD")))
    a, b = cells[:2]
    clues = [
        *(FactClue("f", a, b, status) for status in Status),
        *(BinaryClue("b", a, kind, a, b) for kind in BinaryKind),
        *(
            CountClue("c", a, kind, k, RowRegion(0))
            for kind in CountKind
            for k in range(3)
        ),
    ]
    for clue in clues:
        kb = encoder.encode(board, (clue,), ())
        assert kb.variables.primary == cells
        for values in product(Status, repeat=len(cells)):
            assignment = dict(zip(cells, values))
            expected = evaluator.evaluate(clue, assignment, board)
            assumptions = tuple(
                i if value is Status.CRIMINAL else -i
                for i, value in enumerate(values, 1)
            )
            actual = solver.solve(kb.cnf, kb.variables, assumptions)
            assert (actual.status is SATStatus.SAT) == expected, (clue, assignment)
