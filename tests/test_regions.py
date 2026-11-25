import pytest

from griductive.models import (
    Board,
    Cell,
    Character,
    ColumnRegion,
    ExplicitRegion,
    NeighborRegion,
    RowRegion,
)
from griductive.regions import (
    GridRegionResolver,
    column_index,
    column_label,
    format_cell,
    parse_cell,
)

resolver = GridRegionResolver()


def make_board(size: int) -> Board:
    cells = [Cell(r, c) for r in range(size) for c in range(size)]
    return Board(
        size, tuple(Character(cell, f"P{i:02}", "X") for i, cell in enumerate(cells))
    )


def names(cells) -> list[str]:
    return [format_cell(cell) for cell in cells]


# --------------------------------------------------------------------------
# Coordinates


@pytest.mark.parametrize(
    "text,cell",
    [("A1", Cell(0, 0)), ("C2", Cell(1, 2)), ("E5", Cell(4, 4)), ("AA10", Cell(9, 26))],
)
def test_parse_and_format_coordinates(text, cell):
    assert parse_cell(text) == cell
    assert format_cell(cell) == text


@pytest.mark.parametrize(
    "index,label",
    [(0, "A"), (25, "Z"), (26, "AA"), (27, "AB"), (701, "ZZ"), (702, "AAA")],
)
def test_column_labels_follow_spreadsheet_style(index, label):
    assert column_label(index) == label
    assert column_index(label) == index


def test_column_label_round_trips():
    for index in range(2000):
        assert column_index(column_label(index)) == index


@pytest.mark.parametrize(
    "text", ["", "a1", "A0", "A01", "1A", "A", "B-1", " A1", "A1 ", "Ă1", None, 11]
)
def test_parse_cell_rejects_bad_text(text):
    with pytest.raises(ValueError):
        parse_cell(text)


@pytest.mark.parametrize("bad", [-1, True, 1.0, "A"])
def test_column_label_rejects_bad_index(bad):
    with pytest.raises(ValueError):
        column_label(bad)


# --------------------------------------------------------------------------
# Rows and columns


def test_row_and_column():
    board = make_board(3)
    assert names(resolver.resolve(RowRegion(1), board)) == ["A2", "B2", "C2"]
    assert names(resolver.resolve(ColumnRegion(2), board)) == ["C1", "C2", "C3"]


@pytest.mark.parametrize("region", [RowRegion(3), RowRegion(-1), ColumnRegion(5)])
def test_row_and_column_outside_board(region):
    with pytest.raises(ValueError):
        resolver.resolve(region, make_board(3))


@pytest.mark.parametrize(
    "region", [RowRegion(True), ColumnRegion(False), RowRegion(1.0)]
)
def test_row_and_column_reject_non_integer_index(region):
    with pytest.raises(ValueError):
        resolver.resolve(region, make_board(3))


# --------------------------------------------------------------------------
# Neighbors


@pytest.mark.parametrize(
    "size,center,expected",
    [
        (3, "A1", 3),  # corner
        (3, "B1", 5),  # edge
        (3, "B2", 8),  # interior
        (5, "E5", 3),
        (5, "A3", 5),
        (5, "C3", 8),
        (1, "A1", 0),  # a 1x1 board has no neighbors
    ],
)
def test_neighbor_counts(size, center, expected):
    cells = resolver.resolve(NeighborRegion(parse_cell(center)), make_board(size))
    assert len(cells) == expected
    assert parse_cell(center) not in cells


def test_neighbors_are_row_major_and_do_not_wrap():
    board = make_board(4)
    assert names(resolver.resolve(NeighborRegion(Cell(0, 0)), board)) == [
        "B1",
        "A2",
        "B2",
    ]
    assert names(resolver.resolve(NeighborRegion(parse_cell("D2")), board)) == [
        "C1",
        "D1",
        "C2",
        "C3",
        "D3",
    ]


def test_neighbors_of_cell_outside_board():
    with pytest.raises(ValueError):
        resolver.resolve(NeighborRegion(Cell(3, 0)), make_board(3))


# --------------------------------------------------------------------------
# Explicit lists


def test_explicit_is_sorted_row_major():
    region = ExplicitRegion((parse_cell("C2"), parse_cell("A3"), parse_cell("B1")))
    assert names(resolver.resolve(region, make_board(3))) == ["B1", "C2", "A3"]


def test_explicit_empty_is_valid():
    assert resolver.resolve(ExplicitRegion(()), make_board(3)) == ()


def test_explicit_duplicates_are_rejected():
    region = ExplicitRegion((Cell(0, 0), Cell(1, 1), Cell(0, 0)))
    with pytest.raises(ValueError, match="A1"):
        resolver.resolve(region, make_board(3))


@pytest.mark.parametrize(
    "cells",
    [
        (Cell(0, 3),),  # outside the board
        (Cell(-1, 0),),
        ("A1",),  # text instead of Cell
        (Cell(True, 0),),
    ],
)
def test_explicit_invalid_cells(cells):
    with pytest.raises(ValueError):
        resolver.resolve(ExplicitRegion(cells), make_board(3))


def test_explicit_cells_must_be_a_tuple():
    with pytest.raises(ValueError):
        resolver.resolve(ExplicitRegion([Cell(0, 0)]), make_board(3))


# --------------------------------------------------------------------------
# General contract


def test_unknown_region_type():
    with pytest.raises(ValueError, match="unknown region"):
        resolver.resolve("ROW 1", make_board(3))


@pytest.mark.parametrize("size", [0, -2, True])
def test_invalid_board_size(size):
    with pytest.raises(ValueError):
        resolver.resolve(RowRegion(0), Board(size, ()))


@pytest.mark.parametrize("size", [3, 4, 5])
def test_every_region_is_distinct_and_row_major(size):
    board = make_board(size)
    regions = [RowRegion(i) for i in range(size)]
    regions += [ColumnRegion(i) for i in range(size)]
    regions += [NeighborRegion(c.cell) for c in board.characters]
    for region in regions:
        cells = resolver.resolve(region, board)
        assert list(cells) == sorted(set(cells))


@pytest.mark.parametrize("bad", ["", "a", "A1", "Ă", None, 0])
def test_column_index_rejects_bad_label(bad):
    with pytest.raises(ValueError):
        column_index(bad)


@pytest.mark.parametrize("bad", [Cell(-1, 0), Cell(0, -1), Cell(True, 0), (0, 0)])
def test_format_cell_rejects_bad_cell(bad):
    with pytest.raises(ValueError):
        format_cell(bad)
