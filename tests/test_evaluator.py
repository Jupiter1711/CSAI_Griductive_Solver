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
    ExplicitRegion,
    FactClue,
    IntersectionClue,
    ParityClue,
    ParityKind,
    RowRegion,
    Status,
)

A, B, C, D = (Cell(i // 2, i % 2) for i in range(4))
BOARD = Board(2, tuple(Character(c, n, "") for c, n in zip((A, B, C, D), "ABCD")))
INN, T = Status.INNOCENT, Status.CRIMINAL
VALUES = {A: INN, B: T, C: T, D: INN}


@pytest.mark.parametrize(
    "clue,expected",
    [
        (ParityClue("p", A, ParityKind.EVEN, ExplicitRegion(())), True),
        (ParityClue("p", A, ParityKind.ODD, RowRegion(0)), True),
        (IntersectionClue("i", A, 0, (RowRegion(0), RowRegion(1))), True),
        (IntersectionClue("i", A, 1, (RowRegion(0), ExplicitRegion((B, C)))), True),
        (FactClue("f", A, B, T), True),
        (FactClue("f", A, B, INN), False),
        (BinaryClue("b", A, BinaryKind.SAME, B, C), True),
        (BinaryClue("b", A, BinaryKind.SAME, A, C), False),
        (BinaryClue("b", A, BinaryKind.DIFFERENT, B, C), False),
        (BinaryClue("b", A, BinaryKind.DIFFERENT, A, C), True),
        *[
            (CountClue("c", A, kind, k, RowRegion(0)), expected)
            for kind, results in [
                (CountKind.EXACTLY, (False, True, False)),
                (CountKind.AT_LEAST, (True, True, False)),
                (CountKind.AT_MOST, (False, True, True)),
            ]
            for k, expected in enumerate(results)
        ],
        (CountClue("c", A, CountKind.EXACTLY, 0, ExplicitRegion(())), True),
    ],
)
def test_direct_semantics(clue, expected):
    assert DirectClueEvaluator().evaluate(clue, VALUES, BOARD) is expected


@pytest.mark.parametrize(
    "clue,values",
    [
        (IntersectionClue("i", A, 0, ()), VALUES),
        (IntersectionClue("i", A, 1, (RowRegion(0), RowRegion(1))), VALUES),
        (IntersectionClue("i", A, False, (RowRegion(0),)), VALUES),
        (ParityClue("p", A, "unexpected", RowRegion(0)), VALUES),
        (FactClue("f", A, B, T), {A: INN}),
        (FactClue("f", A, B, T), {**VALUES, Cell(2, 2): T}),
        (FactClue("f", A, B, T), {**VALUES, B: "CRIMINAL"}),
        (FactClue("f", A, Cell(False, 0), T), VALUES),
        (FactClue("f", Cell(2, 0), A, T), VALUES),
        *[
            (CountClue("c", A, CountKind.EXACTLY, k, RowRegion(0)), VALUES)
            for k in (-1, 3, True)
        ],
    ],
)
def test_invalid_input(clue, values):
    with pytest.raises(ValueError):
        DirectClueEvaluator().evaluate(clue, values, BOARD)
