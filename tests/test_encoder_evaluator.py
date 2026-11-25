"""Exhaustive semantic comparison for the team's concrete encoder."""

from itertools import product

from cnf_helpers import is_cnf_satisfiable_with_primary_assignment

from griductive.encoder import BasicCNFEncoder
from griductive.evaluator import DirectClueEvaluator
from griductive.models import (
    BinaryClue,
    BinaryKind,
    Board,
    Cell,
    Character,
    CountClue,
    CountKind,
    ExplicitRegion,
    FactClue,
    IntersectionClue,
    ParityClue,
    ParityKind,
    RowRegion,
    Status,
)


def test_encoded_clue_matches_direct_semantics():
    encoder = BasicCNFEncoder()
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
        *(
            ParityClue("p", a, kind, region)
            for kind in ParityKind
            for region in (ExplicitRegion(()), ExplicitRegion(cells))
        ),
        *(
            IntersectionClue(
                "i", a, k, (RowRegion(0), ExplicitRegion((a, b, cells[2])))
            )
            for k in range(3)
        ),
        IntersectionClue("empty", a, 0, (RowRegion(0), RowRegion(1))),
    ]
    for clue in clues:
        kb = encoder.encode(board, (clue,), ())
        assert kb.variables.primary == cells
        for values in product(Status, repeat=len(cells)):
            assignment = dict(zip(cells, values))
            expected = evaluator.evaluate(clue, assignment, board)
            primary = {i: value is Status.CRIMINAL for i, value in enumerate(values, 1)}
            actual = is_cnf_satisfiable_with_primary_assignment(
                kb.cnf, primary, kb.variables.auxiliary_count
            )
            assert actual == expected, (clue, assignment)
