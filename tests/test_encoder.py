from itertools import product

import pytest
from cnf_helpers import is_cnf_satisfiable_with_primary_assignment

from griductive.encoder import BasicCNFEncoder
from griductive.models import (
    BinaryClue,
    BinaryKind,
    Board,
    Cell,
    Character,
    ColumnRegion,
    CountClue,
    CountKind,
    ExplicitRegion,
    FactClue,
    IntersectionClue,
    ParityClue,
    ParityKind,
    RowRegion,
    Status,
    Verdict,
)


@pytest.fixture
def board():
    return Board(
        size=2,
        characters=(
            Character(Cell(0, 0), "A", "Doctor"),
            Character(Cell(0, 1), "B", "Teacher"),
            Character(Cell(1, 0), "C", "Lawyer"),
            Character(Cell(1, 1), "D", "Artist"),
        ),
    )


@pytest.fixture
def encoder():
    return BasicCNFEncoder()


def test_primary_variables_are_row_major(board, encoder):
    encoded = encoder.encode(board, (), ())

    assert encoded.variables.primary == (
        Cell(0, 0),
        Cell(0, 1),
        Cell(1, 0),
        Cell(1, 1),
    )


def test_fact_criminal(board, encoder):
    clue = FactClue(
        id="F1",
        owner=Cell(0, 0),
        target=Cell(0, 1),
        status=Status.CRIMINAL,
    )

    encoded = encoder.encode(board, (clue,), ())

    assert encoded.cnf == ((2,),)


def test_fact_innocent(board, encoder):
    clue = FactClue(
        id="F2",
        owner=Cell(0, 0),
        target=Cell(1, 0),
        status=Status.INNOCENT,
    )

    encoded = encoder.encode(board, (clue,), ())

    assert encoded.cnf == ((-3,),)


def test_invalid_status_rejected_for_fact_and_verdict(board, encoder):
    cell = Cell(0, 0)
    with pytest.raises(ValueError):
        encoder.encode(board, (FactClue("f", cell, cell, "TYPO"),), ())
    with pytest.raises(ValueError):
        encoder.encode(board, (), (Verdict(cell, "TYPO"),))


@pytest.mark.parametrize("k", [True, False, 1.0, "1"])
def test_count_parameters_require_integers(board, encoder, k):
    cell = Cell(0, 0)
    region = RowRegion(0)
    for clue in (
        CountClue("c", cell, CountKind.EXACTLY, k, region),
        IntersectionClue("i", cell, k, (region,)),
    ):
        with pytest.raises(ValueError):
            encoder.encode(board, (clue,), ())


def test_binary_same(board, encoder):
    clue = BinaryClue(
        id="B1",
        owner=Cell(0, 0),
        kind=BinaryKind.SAME,
        left=Cell(0, 0),
        right=Cell(0, 1),
    )

    encoded = encoder.encode(board, (clue,), ())

    assert encoded.cnf == (
        (-1, 2),
        (1, -2),
    )


def test_binary_different(board, encoder):
    clue = BinaryClue(
        id="B2",
        owner=Cell(0, 0),
        kind=BinaryKind.DIFFERENT,
        left=Cell(0, 0),
        right=Cell(0, 1),
    )

    encoded = encoder.encode(board, (clue,), ())

    assert encoded.cnf == (
        (1, 2),
        (-1, -2),
    )


def test_verdict_criminal(board, encoder):
    verdict = Verdict(
        cell=Cell(1, 1),
        status=Status.CRIMINAL,
    )

    encoded = encoder.encode(board, (), (verdict,))

    assert encoded.cnf == ((4,),)


def test_verdict_innocent(board, encoder):
    verdict = Verdict(
        cell=Cell(1, 1),
        status=Status.INNOCENT,
    )

    encoded = encoder.encode(board, (), (verdict,))

    assert encoded.cnf == ((-4,),)


def test_multiple_clues_are_combined(board, encoder):
    clues = (
        FactClue(
            id="F1",
            owner=Cell(0, 0),
            target=Cell(0, 1),
            status=Status.CRIMINAL,
        ),
        FactClue(
            id="F2",
            owner=Cell(0, 0),
            target=Cell(1, 0),
            status=Status.INNOCENT,
        ),
    )

    verdicts = (Verdict(Cell(1, 1), Status.CRIMINAL),)

    encoded = encoder.encode(board, clues, verdicts)

    assert encoded.cnf == (
        (2,),
        (-3,),
        (4,),
    )


def test_contradiction_is_valid_cnf(board, encoder):
    clues = (
        FactClue(
            id="F1",
            owner=Cell(0, 0),
            target=Cell(0, 1),
            status=Status.CRIMINAL,
        ),
        FactClue(
            id="F2",
            owner=Cell(0, 0),
            target=Cell(0, 1),
            status=Status.INNOCENT,
        ),
    )

    encoded = encoder.encode(board, clues, ())

    assert encoded.cnf == (
        (2,),
        (-2,),
    )


@pytest.mark.parametrize(
    "kind",
    [
        CountKind.AT_MOST,
        CountKind.AT_LEAST,
        CountKind.EXACTLY,
    ],
)
@pytest.mark.parametrize("k", range(5))
def test_count_clue_logic(encoder, board, kind, k):
    clue = CountClue(
        id="C1",
        owner=Cell(0, 0),
        kind=kind,
        k=k,
        region=ExplicitRegion(
            cells=tuple(character.cell for character in board.characters)
        ),
    )

    encoded = encoder.encode(board, (clue,), ())

    primary_count = len(encoded.variables.primary)
    auxiliary_count = encoded.variables.auxiliary_count

    # Thử toàn bộ 2^4 cách gán biến chính
    for values in product((False, True), repeat=primary_count):
        primary_assignment = {i + 1: values[i] for i in range(primary_count)}

        criminal_count = sum(values)

        if kind == CountKind.AT_MOST:
            expected = criminal_count <= k

        elif kind == CountKind.AT_LEAST:
            expected = criminal_count >= k

        else:
            expected = criminal_count == k

        actual = is_cnf_satisfiable_with_primary_assignment(
            encoded.cnf,
            primary_assignment,
            auxiliary_count,
        )

        assert actual == expected


def test_count_clue_invalid_k_raises_value_error(encoder, board):
    clue = CountClue(
        id="C1",
        owner=Cell(0, 0),
        kind=CountKind.EXACTLY,
        k=5,
        region=ExplicitRegion(
            cells=tuple(character.cell for character in board.characters)
        ),
    )

    with pytest.raises(ValueError):
        encoder.encode(board, (clue,), ())


@pytest.mark.parametrize(
    "kind",
    [
        ParityKind.EVEN,
        ParityKind.ODD,
    ],
)
def test_parity_clue_logic(encoder, board, kind):
    cells = tuple(character.cell for character in board.characters)

    clue = ParityClue(
        id="P1",
        owner=Cell(0, 0),
        kind=kind,
        region=ExplicitRegion(cells=cells),
    )

    encoded = encoder.encode(board, (clue,), ())

    primary_count = len(encoded.variables.primary)
    auxiliary_count = encoded.variables.auxiliary_count

    for values in product((False, True), repeat=primary_count):
        primary_assignment = {i + 1: values[i] for i in range(primary_count)}

        criminal_count = sum(values)

        if kind == ParityKind.EVEN:
            expected = criminal_count % 2 == 0
        else:
            expected = criminal_count % 2 == 1

        actual = is_cnf_satisfiable_with_primary_assignment(
            encoded.cnf,
            primary_assignment,
            auxiliary_count,
        )

        assert actual == expected


@pytest.mark.parametrize(
    ("kind", "expected_cnf"),
    [
        (ParityKind.EVEN, ()),
        (ParityKind.ODD, ((),)),
    ],
)
def test_parity_clue_empty_region(
    encoder,
    board,
    kind,
    expected_cnf,
):
    clue = ParityClue(
        id="P2",
        owner=Cell(0, 0),
        kind=kind,
        region=ExplicitRegion(cells=()),
    )

    encoded = encoder.encode(board, (clue,), ())

    assert encoded.cnf == expected_cnf


@pytest.mark.parametrize(
    ("regions", "intersection_cells"),
    [
        (
            (RowRegion(0), ColumnRegion(0)),
            (Cell(0, 0),),
        ),
        (
            (
                RowRegion(0),
                ExplicitRegion(
                    cells=(
                        Cell(0, 0),
                        Cell(0, 1),
                    )
                ),
            ),
            (
                Cell(0, 0),
                Cell(0, 1),
            ),
        ),
    ],
)
def test_intersection_clue_logic(
    encoder,
    board,
    regions,
    intersection_cells,
):
    for k in range(len(intersection_cells) + 1):
        clue = IntersectionClue(
            id="I1",
            owner=Cell(0, 0),
            k=k,
            regions=regions,
        )

        encoded = encoder.encode(board, (clue,), ())

        primary_count = len(encoded.variables.primary)
        auxiliary_count = encoded.variables.auxiliary_count

        for values in product((False, True), repeat=primary_count):
            primary_assignment = {i + 1: values[i] for i in range(primary_count)}

            criminal_count = sum(
                values[encoded.variables.primary.index(cell)]
                for cell in intersection_cells
            )

            expected = criminal_count == k

            actual = is_cnf_satisfiable_with_primary_assignment(
                encoded.cnf,
                primary_assignment,
                auxiliary_count,
            )

            assert actual == expected


def test_intersection_clue_invalid_k_raises_value_error(
    encoder,
    board,
):
    clue = IntersectionClue(
        id="I2",
        owner=Cell(0, 0),
        k=2,
        regions=(
            RowRegion(0),
            ColumnRegion(0),
        ),
    )

    with pytest.raises(ValueError):
        encoder.encode(board, (clue,), ())


def test_verdict_invalid_cell_raises_value_error(
    encoder,
    board,
):
    verdict = Verdict(
        cell=Cell(2, 0),
        status=Status.CRIMINAL,
    )

    with pytest.raises(ValueError):
        encoder.encode(board, (), (verdict,))


def test_fact_clue_invalid_target_raises_value_error(
    encoder,
    board,
):
    clue = FactClue(
        id="F_INVALID",
        owner=Cell(0, 0),
        target=Cell(2, 0),
        status=Status.CRIMINAL,
    )

    with pytest.raises(ValueError):
        encoder.encode(board, (clue,), ())


def test_count_clue_invalid_row_region_raises_value_error(
    encoder,
    board,
):
    clue = CountClue(
        id="C_INVALID_REGION",
        owner=Cell(0, 0),
        kind=CountKind.EXACTLY,
        k=0,
        region=RowRegion(2),
    )

    with pytest.raises(ValueError):
        encoder.encode(board, (clue,), ())


def test_count_clue_invalid_explicit_region_raises_value_error(
    encoder,
    board,
):
    clue = CountClue(
        id="C_INVALID_REGION",
        owner=Cell(0, 0),
        kind=CountKind.EXACTLY,
        k=0,
        region=ExplicitRegion(
            cells=(Cell(2, 0),),
        ),
    )

    with pytest.raises(ValueError):
        encoder.encode(board, (clue,), ())
