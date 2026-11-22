"""Checks for the scaffold, not claims about unimplemented algorithms."""

import importlib
import inspect
from dataclasses import FrozenInstanceError, fields
from typing import get_type_hints

import pytest

CONTRACTS = [
    ("puzzle_io", "PuzzleLoader"),
    ("regions", "RegionResolver"),
    ("encoder", "CNFEncoder"),
    ("evaluator", "ClueEvaluator"),
    ("solver", "SATSolver"),
    ("engine", "GameEngine"),
    ("agent.inference", "LogicAgent"),
    ("agent.runner", "DeductionRunner"),
    ("validation", "PuzzleValidator"),
    ("benchmark", "BenchmarkRunner"),
    ("gui", "GameUI"),
]


@pytest.mark.parametrize("module,name", CONTRACTS)
def test_contract_requires_implementation(module, name):
    contract = getattr(importlib.import_module(f"griductive.{module}"), name)
    assert inspect.isabstract(contract)
    with pytest.raises(TypeError):
        contract()
    for method in contract.__abstractmethods__:
        hints = get_type_hints(getattr(contract, method))
        assert "return" in hints


def test_public_state_has_only_public_payload_and_is_immutable():
    from griductive.models import Board, Cell, Character, PublicState, Status, Verdict

    cell = Cell(0, 0)
    board = Board(1, (Character(cell, "An", "Doctor"),))
    state = PublicState(board, (Verdict(cell, Status.INNOCENT),), ())
    assert {field.name for field in fields(state)} == {"board", "verdicts", "clues"}
    assert {field.name for field in fields(board)} == {"size", "characters"}
    assert {field.name for field in fields(board.characters[0])} == {
        "cell",
        "name",
        "profession",
    }
    with pytest.raises(FrozenInstanceError):
        state.clues = ()
    with pytest.raises(FrozenInstanceError):
        state.board.characters[0].name = "Changed"


def test_cells_sort_in_row_major_order():
    from griductive.models import Cell

    assert sorted([Cell(1, 0), Cell(0, 1), Cell(0, 0)]) == [
        Cell(0, 0),
        Cell(0, 1),
        Cell(1, 0),
    ]
