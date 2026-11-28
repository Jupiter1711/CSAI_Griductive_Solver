"""Coordinate/region contract. Owner: Hồ Trần Quốc Thắng."""

import re
from abc import ABC, abstractmethod

from griductive.models import (
    Board,
    Cell,
    ColumnRegion,
    ExplicitRegion,
    NeighborRegion,
    Region,
    RowRegion,
)

_COLUMN = re.compile(r"[A-Z]+")
_COORDINATE = re.compile(r"([A-Z]+)([1-9][0-9]*)")


class RegionResolver(ABC):
    @abstractmethod
    def resolve(self, region: Region, board: Board) -> tuple[Cell, ...]:
        """Return distinct cells in row-major order; ValueError for invalid input.

        Neighbors include diagonals but exclude self. Reject out-of-board
        references and duplicates in explicit lists. Empty explicit lists are
        valid; no wrapping across board boundaries.
        """
        raise NotImplementedError


class GridRegionResolver(RegionResolver):
    def resolve(self, region: Region, board: Board) -> tuple[Cell, ...]:
        size = _board_size(board)

        if isinstance(region, RowRegion):
            row = _index(region.row, size, "row")
            return tuple(Cell(row, col) for col in range(size))

        if isinstance(region, ColumnRegion):
            col = _index(region.col, size, "column")
            return tuple(Cell(row, col) for row in range(size))

        if isinstance(region, NeighborRegion):
            center = validate_cell(region.cell, size)
            return tuple(
                Cell(row, col)
                for row in range(center.row - 1, center.row + 2)
                for col in range(center.col - 1, center.col + 2)
                if 0 <= row < size
                and 0 <= col < size
                and (row, col) != (center.row, center.col)
            )

        if isinstance(region, ExplicitRegion):
            if not isinstance(region.cells, tuple):
                raise ValueError("explicit region cells must be a tuple")
            cells = [validate_cell(cell, size) for cell in region.cells]
            duplicates = sorted({cell for cell in cells if cells.count(cell) > 1})
            if duplicates:
                names = ", ".join(format_cell(cell) for cell in duplicates)
                raise ValueError(f"explicit region repeats cells: {names}")
            return tuple(sorted(cells))

        raise ValueError(f"unknown region type: {type(region).__name__}")


def intersect_regions(
    regions: tuple[Region, ...],
    board: Board,
    resolver: RegionResolver | None = None,
) -> tuple[Cell, ...]:
    if not isinstance(regions, tuple) or len(regions) < 2:
        raise ValueError("an intersection needs a tuple of at least two regions")
    resolver = resolver or GridRegionResolver()
    shared = set(resolver.resolve(regions[0], board))
    for region in regions[1:]:
        shared &= set(resolver.resolve(region, board))
    return tuple(sorted(shared))


def column_label(col: int) -> str:
    """0 -> "A", 25 -> "Z", 26 -> "AA", bijective base 26."""
    if not _is_int(col) or col < 0:
        raise ValueError(f"col must be a non-negative, got {col!r}")
    label = ""
    number = col + 1
    while number:
        number, remainder = divmod(number - 1, 26)
        label = chr(ord("A") + remainder) + label
    return label


def column_index(label: str) -> int:
    """Inverse column label: "A" -> 0, "Z" -> 25, "AA" -> 26"""
    if not isinstance(label, str) or not _COLUMN.fullmatch(label):
        raise ValueError(f"column must be uppercase letters, got {label!r}")
    number = 0
    for char in label:
        number = number * 26 + (ord(char) - ord("A") + 1)
    return number - 1


def parse_cell(text: str) -> Cell:
    """Parse "C2" into (1,2)"""
    match = _COORDINATE.fullmatch(text) if isinstance(text, str) else None
    if match is None:
        raise ValueError(f"Invalid coordinate {text!r}")
    letters, digits = match.groups()
    return Cell(int(digits) - 1, column_index(letters))


def format_cell(cell: Cell) -> str:
    """(1,2) -> C2"""
    if not isinstance(cell, Cell) or not _is_int(cell.row) or cell.row < 0:
        raise ValueError(f"not a valid cell, got {cell!r}")
    return f"{column_label(cell.col)}{cell.row + 1}"


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _board_size(board: Board) -> int:
    size = getattr(board, "size", None)
    if not _is_int(size) or size < 1:
        raise ValueError(f"Board size must be a positive integer, got {size!r}")
    return size


def _index(value: object, size: int, what: str) -> int:
    if not _is_int(value) or not 0 <= value < size:
        raise ValueError(f"{what} index {value!r} is outside a {size}x{size} board")
    return value


def validate_cell(cell: object, size: int) -> Cell:
    if not isinstance(cell, Cell):
        raise ValueError(f"expected a Cell, got {cell!r}")
    if not (_is_int(cell.row) and _is_int(cell.col)):
        raise ValueError(f"cell indices must be integers, got {cell!r}")
    if not (0 <= cell.row < size and 0 <= cell.col < size):
        raise ValueError(f"cell {cell!r} is outside a {size}x{size} board")
    return cell
