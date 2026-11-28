"""JSON loading contract. Puzzle data owner: Hồ Trần Quốc Thắng."""

import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from griductive.models import (
    BinaryClue,
    BinaryKind,
    Board,
    Cell,
    Character,
    Clue,
    ColumnRegion,
    CountClue,
    CountKind,
    ExplicitRegion,
    FactClue,
    IntersectionClue,
    NeighborRegion,
    ParityClue,
    ParityKind,
    Puzzle,
    Region,
    RowRegion,
    Status,
    Verdict,
)
from griductive.regions import (
    GridRegionResolver,
    column_index,
    format_cell,
    intersect_regions,
    parse_cell,
)


class PuzzleLoader(ABC):
    @abstractmethod
    def load(self, path: Path) -> Puzzle:
        """Read the JSON schema in docs/architecture.md into immutable records.

        Validate shape, ids, coordinates, enums, clue parameters, full solution
        and initial reveals. Raise ValueError for invalid content, OSError for
        I/O failures. Semantic/uniqueness checks belong to PuzzleValidator.
        """
        raise NotImplementedError


_TOP_KEYS = {"id", "size", "characters", "clues", "solution", "initially_revealed"}
_CHARACTER_KEYS = {"cell", "name", "profession"}
_CLUE_KEYS = {
    "FACT": {"target", "status"},
    "SAME": {"left", "right"},
    "DIFFERENT": {"left", "right"},
    "EXACTLY": {"k", "region"},
    "AT_LEAST": {"k", "region"},
    "AT_MOST": {"k", "region"},
    "PARITY": {"parity", "region"},
    "INTERSECTION": {"k", "regions"},
}
_REGION_KEYS = {
    "ROW": {"row"},
    "COLUMN": {"column"},
    "NEIGHBORS": {"cell"},
    "EXPLICIT": {"cells"},
}


class JsonPuzzleLoader(PuzzleLoader):
    """Strict reader: rejects anything the schema does not allow, never repairs."""

    def load(self, path: Path) -> Puzzle:
        raw = Path(path).read_bytes()
        try:
            data = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
            return _puzzle(data)
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc


def _puzzle(data: Any) -> Puzzle:
    _keys(data, _TOP_KEYS, "puzzle")
    puzzle_id = _text(data["id"], "id")
    size = _integer(data["size"], "size")
    if size < 1:
        raise ValueError(f"size: must be at least 1, got {size}")
    _list(data["characters"], "characters", size * size)
    cells = [Cell(row, col) for row in range(size) for col in range(size)]

    characters = _characters(data["characters"], cells, size)
    board = Board(size, characters)
    clues = _clues(data["clues"], board, cells)
    solution = _solution(data["solution"], cells, size)
    revealed = _cell_list(data["initially_revealed"], size, "initially_revealed")
    return Puzzle(puzzle_id, board, clues, solution, revealed)


def _characters(items: Any, cells: list[Cell], size: int) -> tuple[Character, ...]:
    result = []
    for i, (item, expected) in enumerate(zip(items, cells)):
        where = f"characters[{i}]"
        _keys(item, _CHARACTER_KEYS, where)
        cell = _cell(item["cell"], size, f"{where}.cell")
        if cell != expected:
            raise ValueError(
                f"{where}.cell: expected {format_cell(expected)} (row-major order), "
                f"got {item['cell']}"
            )
        name = _text(item["name"], f"{where}.name")
        profession = _text(item["profession"], f"{where}.profession")
        if result and name.casefold() <= result[-1].name.casefold():
            raise ValueError(
                f"{where}.name: names must be unique and alphabetical in "
                f"row-major order, {name!r} comes after {result[-1].name!r}"
            )
        result.append(Character(cell, name, profession))
    return tuple(result)


def _clues(items: Any, board: Board, cells: list[Cell]) -> tuple[Clue, ...]:
    _list(items, "clues", len(cells))
    by_owner: dict[Cell, Clue] = {}
    ids: set[str] = set()
    for i, item in enumerate(items):
        where = f"clues[{i}]"
        clue = _clue(item, board, where)
        if clue.id in ids:
            raise ValueError(f"{where}.id: duplicate clue id {clue.id!r}")
        if clue.owner in by_owner:
            raise ValueError(f"{where}.owner: {item['owner']} already owns a clue")
        ids.add(clue.id)
        by_owner[clue.owner] = clue
    return tuple(by_owner[cell] for cell in cells)


def _clue(item: Any, board: Board, where: str) -> Clue:
    if not isinstance(item, dict):
        raise ValueError(f"{where}: expected an object")
    kind = _enum(item.get("type"), _CLUE_KEYS, f"{where}.type")
    _keys(item, {"id", "owner", "type"} | _CLUE_KEYS[kind], where)
    clue_id = _text(item["id"], f"{where}.id")
    owner = _cell(item["owner"], board.size, f"{where}.owner")

    if kind == "FACT":
        target = _cell(item["target"], board.size, f"{where}.target")
        status = Status(_enum(item["status"], Status.__members__, f"{where}.status"))
        return FactClue(clue_id, owner, target, status)

    if kind in ("SAME", "DIFFERENT"):
        left = _cell(item["left"], board.size, f"{where}.left")
        right = _cell(item["right"], board.size, f"{where}.right")
        return BinaryClue(clue_id, owner, BinaryKind(kind), left, right)

    if kind == "PARITY":
        region = _region(item["region"], board.size, f"{where}.region")
        parity = _enum(item["parity"], ParityKind.__members__, f"{where}.parity")
        return ParityClue(clue_id, owner, ParityKind(parity), region)

    if kind == "INTERSECTION":
        _list(item["regions"], f"{where}.regions")
        if len(item["regions"]) < 2:
            raise ValueError(f"{where}.regions: expected at least two regions")
        regions = tuple(
            _region(region, board.size, f"{where}.regions[{i}]")
            for i, region in enumerate(item["regions"])
        )
        k = _integer(item["k"], f"{where}.k")
        _check_k(k, len(intersect_regions(regions, board)), where)
        return IntersectionClue(clue_id, owner, k, regions)

    region = _region(item["region"], board.size, f"{where}.region")
    k = _integer(item["k"], f"{where}.k")
    _check_k(k, len(GridRegionResolver().resolve(region, board)), where)
    return CountClue(clue_id, owner, CountKind(kind), k, region)


def _check_k(k: int, region_size: int, where: str) -> None:
    if not 0 <= k <= region_size:
        raise ValueError(f"{where}.k: must be in [0, {region_size}], got {k}")


def _region(item: Any, size: int, where: str) -> Region:
    if not isinstance(item, dict):
        raise ValueError(f"{where}: expected an object")
    kind = _enum(item.get("type"), _REGION_KEYS, f"{where}.type")
    _keys(item, {"type"} | _REGION_KEYS[kind], where)
    if kind == "ROW":
        row = _integer(item["row"], f"{where}.row")
        if not 1 <= row <= size:
            raise ValueError(f"{where}.row: must be in [1, {size}], got {row}")
        return RowRegion(row - 1)
    if kind == "COLUMN":
        col = _parse(column_index, item["column"], f"{where}.column")
        if col >= size:
            raise ValueError(f"{where}.column: {item['column']} is outside the board")
        return ColumnRegion(col)
    if kind == "NEIGHBORS":
        return NeighborRegion(_cell(item["cell"], size, f"{where}.cell"))
    cells = _cell_list(item["cells"], size, f"{where}.cells")
    return ExplicitRegion(tuple(sorted(cells)))


def _solution(item: Any, cells: list[Cell], size: int) -> tuple[Verdict, ...]:
    if not isinstance(item, dict):
        raise ValueError("solution: expected an object of coordinate -> status")
    statuses: dict[Cell, Status] = {}
    for key, value in item.items():
        cell = _cell(key, size, f"solution.{key}")
        name = _enum(value, Status.__members__, f"solution.{key}")
        statuses[cell] = Status(name)
    missing = [format_cell(cell) for cell in cells if cell not in statuses]
    if missing:
        raise ValueError(f"solution: missing {', '.join(missing)}")
    return tuple(Verdict(cell, statuses[cell]) for cell in cells)


def _cell_list(items: Any, size: int, where: str) -> tuple[Cell, ...]:
    _list(items, where)
    result: list[Cell] = []
    for i, text in enumerate(items):
        cell = _cell(text, size, f"{where}[{i}]")
        if cell in result:
            raise ValueError(f"{where}[{i}]: duplicate cell {text}")
        result.append(cell)
    return tuple(result)


def _cell(text: Any, size: int, where: str) -> Cell:
    cell = _parse(parse_cell, text, where)
    if cell.row >= size or cell.col >= size:
        raise ValueError(f"{where}: {text} is outside a {size}x{size} board")
    return cell


def _parse(parser: Callable[[str], Any], text: Any, where: str) -> Any:
    try:
        return parser(text)
    except ValueError as exc:
        raise ValueError(f"{where}: {exc}") from exc


def _keys(item: Any, expected: set[str], where: str) -> None:
    if not isinstance(item, dict):
        raise ValueError(f"{where}: expected an object")
    missing = sorted(expected - item.keys())
    unknown = sorted(item.keys() - expected)
    if missing:
        raise ValueError(f"{where}: missing key(s) {', '.join(missing)}")
    if unknown:
        raise ValueError(f"{where}: unknown key(s) {', '.join(unknown)}")


def _list(item: Any, where: str, length: int | None = None) -> None:
    if not isinstance(item, list):
        raise ValueError(f"{where}: expected an array")
    if length is not None and len(item) != length:
        raise ValueError(f"{where}: expected {length} entries, got {len(item)}")


def _text(item: Any, where: str) -> str:
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{where}: expected a non-empty string")
    return item


def _integer(item: Any, where: str) -> int:
    if not isinstance(item, int) or isinstance(item, bool):
        raise ValueError(f"{where}: expected an integer, got {item!r}")
    return item


def _enum(item: Any, allowed, where: str) -> str:
    if not isinstance(item, str) or item not in allowed:
        raise ValueError(f"{where}: expected one of {', '.join(allowed)}, got {item!r}")
    return item


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result
