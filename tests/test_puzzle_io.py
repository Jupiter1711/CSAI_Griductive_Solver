import copy
import json
from pathlib import Path

import pytest

from griductive.evaluator import DirectClueEvaluator
from griductive.models import (
    BinaryClue,
    BinaryKind,
    Cell,
    ColumnRegion,
    CountClue,
    CountKind,
    ExplicitRegion,
    FactClue,
    NeighborRegion,
    RowRegion,
    Status,
)
from griductive.puzzle_io import JsonPuzzleLoader

PUZZLES = sorted((Path(__file__).resolve().parents[1] / "puzzles").glob("*.json"))

VALID = {
    "id": "tiny",
    "size": 2,
    "characters": [
        {"cell": "A1", "name": "Bulma", "profession": "Scientist"},
        {"cell": "B1", "name": "Goku", "profession": "Saiyan"},
        {"cell": "A2", "name": "Krillin", "profession": "Monk"},
        {"cell": "B2", "name": "Vegeta", "profession": "Prince"},
    ],
    "clues": [
        {
            "id": "c1",
            "owner": "A1",
            "type": "FACT",
            "target": "B1",
            "status": "CRIMINAL",
        },
        {"id": "c2", "owner": "B1", "type": "SAME", "left": "A1", "right": "B2"},
        {
            "id": "c3",
            "owner": "A2",
            "type": "AT_MOST",
            "k": 1,
            "region": {"type": "NEIGHBORS", "cell": "A2"},
        },
        {
            "id": "c4",
            "owner": "B2",
            "type": "EXACTLY",
            "k": 1,
            "region": {"type": "EXPLICIT", "cells": ["B2", "A1"]},
        },
    ],
    "solution": {
        "A1": "INNOCENT",
        "B1": "CRIMINAL",
        "A2": "INNOCENT",
        "B2": "INNOCENT",
    },
    "initially_revealed": ["A1"],
}


def write(tmp_path: Path, data) -> Path:
    path = tmp_path / "puzzle.json"
    text = data if isinstance(data, str) else json.dumps(data)
    path.write_text(text, encoding="utf-8")
    return path


def changed(edit) -> dict:
    data = copy.deepcopy(VALID)
    edit(data)
    return data


def test_loads_valid_puzzle_into_records(tmp_path):
    puzzle = JsonPuzzleLoader().load(write(tmp_path, VALID))
    assert puzzle.id == "tiny"
    assert [c.cell for c in puzzle.board.characters] == [
        Cell(0, 0),
        Cell(0, 1),
        Cell(1, 0),
        Cell(1, 1),
    ]
    assert puzzle.clues == (
        FactClue("c1", Cell(0, 0), Cell(0, 1), Status.CRIMINAL),
        BinaryClue("c2", Cell(0, 1), BinaryKind.SAME, Cell(0, 0), Cell(1, 1)),
        CountClue("c3", Cell(1, 0), CountKind.AT_MOST, 1, NeighborRegion(Cell(1, 0))),
        CountClue(
            "c4",
            Cell(1, 1),
            CountKind.EXACTLY,
            1,
            ExplicitRegion((Cell(0, 0), Cell(1, 1))),
        ),
    )
    assert [v.status for v in puzzle.solution] == [
        Status.INNOCENT,
        Status.CRIMINAL,
        Status.INNOCENT,
        Status.INNOCENT,
    ]
    assert puzzle.initially_revealed == (Cell(0, 0),)


def test_clues_are_returned_in_row_major_owner_order(tmp_path):
    data = changed(lambda d: d["clues"].reverse())
    puzzle = JsonPuzzleLoader().load(write(tmp_path, data))
    assert [clue.owner for clue in puzzle.clues] == [
        Cell(0, 0),
        Cell(0, 1),
        Cell(1, 0),
        Cell(1, 1),
    ]


@pytest.mark.parametrize(
    "region,expected",
    [
        ({"type": "ROW", "row": 2}, RowRegion(1)),
        ({"type": "COLUMN", "column": "B"}, ColumnRegion(1)),
    ],
)
def test_row_and_column_regions_are_one_based_in_json(tmp_path, region, expected):
    def edit(d):
        d["clues"][3]["region"] = region

    puzzle = JsonPuzzleLoader().load(write(tmp_path, changed(edit)))
    assert puzzle.clues[3].region == expected


def _set(path: list, value):
    def edit(d):
        target = d
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return edit


def _delete(path: list):
    def edit(d):
        target = d
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]

    return edit


@pytest.mark.parametrize(
    "edit,where",
    [
        (_set(["extra"], 1), "unknown key"),
        (_delete(["initially_revealed"]), "missing key"),
        (_set(["size"], True), "size"),
        (_set(["size"], 3), "characters"),
        (_set(["id"], ""), "id"),
        (_set(["characters", 1, "cell"], "A2"), "characters[1].cell"),
        (_set(["characters", 1, "name"], "Bulma"), "characters[1].name"),
        (_set(["characters", 1, "name"], "Abe"), "alphabetical"),
        (_set(["characters", 0, "age"], 30), "characters[0]"),
        (_set(["clues", 1, "id"], "c1"), "duplicate clue id"),
        (_set(["clues", 1, "owner"], "A1"), "already owns"),
        (_set(["clues", 0, "type"], "MAYBE"), "clues[0].type"),
        (_set(["clues", 0, "status"], "GUILTY"), "clues[0].status"),
        (_set(["clues", 0, "target"], "C1"), "outside"),
        (_set(["clues", 0, "target"], "a1"), "clues[0].target"),
        (_set(["clues", 0, "target"], "A0"), "clues[0].target"),
        (_set(["clues", 1, "k"], 1), "unknown key"),
        (_set(["clues", 2, "k"], True), "clues[2].k"),
        (_set(["clues", 2, "k"], 4), "must be in [0, 3]"),
        (_set(["clues", 2, "k"], -1), "must be in [0, 3]"),
        (_set(["clues", 2, "region"], {"type": "ROW", "row": 0}), "region.row"),
        (_set(["clues", 2, "region"], {"type": "COLUMN", "column": "C"}), "column"),
        (_set(["clues", 2, "region"], {"type": "DIAGONAL"}), "region.type"),
        (_set(["clues", 3, "region", "cells"], ["A1", "A1"]), "duplicate cell"),
        (_delete(["solution", "B2"]), "missing B2"),
        (_set(["solution", "C3"], "INNOCENT"), "solution.C3"),
        (_set(["solution", "A1"], "innocent"), "solution.A1"),
        (_set(["initially_revealed"], ["A1", "A1"]), "duplicate cell"),
        (_set(["initially_revealed"], ["Z9"]), "outside"),
    ],
)
def test_rejects_invalid_content_with_its_location(tmp_path, edit, where):
    with pytest.raises(ValueError, match=r"puzzle\.json") as error:
        JsonPuzzleLoader().load(write(tmp_path, changed(edit)))
    assert where in str(error.value)


def test_rejects_duplicate_json_keys(tmp_path):
    text = json.dumps(VALID).replace(
        '"A1": "INNOCENT"', '"A1": "INNOCENT", "A1": "CRIMINAL"'
    )
    with pytest.raises(ValueError, match="duplicate key 'A1'"):
        JsonPuzzleLoader().load(write(tmp_path, text))


def test_character_outside_board_is_reported_as_outside(tmp_path):
    data = changed(_set(["characters", 1, "cell"], "C1"))
    with pytest.raises(ValueError, match=r"characters\[1\]\.cell: C1 is outside"):
        JsonPuzzleLoader().load(write(tmp_path, data))


def test_huge_size_is_rejected_before_building_the_board(tmp_path):
    data = changed(_set(["size"], 10**9))
    with pytest.raises(ValueError, match="characters: expected"):
        JsonPuzzleLoader().load(write(tmp_path, data))


def test_non_utf8_file_reports_its_path(tmp_path):
    path = tmp_path / "puzzle.json"
    path.write_bytes(b"\xff\xfe{}")
    with pytest.raises(ValueError, match=r"puzzle\.json"):
        JsonPuzzleLoader().load(path)


def test_rejects_malformed_json(tmp_path):
    with pytest.raises(ValueError):
        JsonPuzzleLoader().load(write(tmp_path, "{not json"))


def test_missing_file_raises_os_error(tmp_path):
    with pytest.raises(OSError):
        JsonPuzzleLoader().load(tmp_path / "missing.json")


@pytest.mark.parametrize("path", PUZZLES, ids=lambda p: p.stem)
def test_shipped_puzzles_load_and_solution_satisfies_every_clue(path):
    puzzle = JsonPuzzleLoader().load(path)
    assignment = {v.cell: v.status for v in puzzle.solution}
    evaluator = DirectClueEvaluator()
    assert all(evaluator.evaluate(c, assignment, puzzle.board) for c in puzzle.clues)
