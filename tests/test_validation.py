from dataclasses import replace
from pathlib import Path

import pytest

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
    FactClue,
    Puzzle,
    RowRegion,
    Status,
    Uniqueness,
    Verdict,
)
from griductive.puzzle_io import JsonPuzzleLoader
from griductive.solver import DPLLSolver
from griductive.validation import SATPuzzleValidator

PUZZLES = sorted((Path(__file__).resolve().parents[1] / "puzzles").glob("*.json"))

A1, B1, A2, B2 = Cell(0, 0), Cell(0, 1), Cell(1, 0), Cell(1, 1)
BOARD = Board(
    2,
    (
        Character(A1, "Bulma", "Scientist"),
        Character(B1, "Goku", "Saiyan"),
        Character(A2, "Krillin", "Monk"),
        Character(B2, "Vegeta", "Prince"),
    ),
)
UNIQUE_CLUES = (
    FactClue("c1", A1, B1, Status.CRIMINAL),
    CountClue("c2", B1, CountKind.EXACTLY, 1, RowRegion(0)),
    BinaryClue("c3", A2, BinaryKind.DIFFERENT, B1, A2),
    BinaryClue("c4", B2, BinaryKind.SAME, A1, B2),
)
SOLUTION = (
    Verdict(A1, Status.INNOCENT),
    Verdict(B1, Status.CRIMINAL),
    Verdict(A2, Status.INNOCENT),
    Verdict(B2, Status.INNOCENT),
)
PUZZLE = Puzzle("tiny", BOARD, UNIQUE_CLUES, SOLUTION, (A1,))


@pytest.fixture
def validator() -> SATPuzzleValidator:
    return SATPuzzleValidator(BasicCNFEncoder(), DPLLSolver(), DirectClueEvaluator())


def test_unique_puzzle_is_valid(validator):
    result = validator.validate(PUZZLE)
    assert result.errors == ()
    assert result.uniqueness is Uniqueness.UNIQUE


def test_two_solutions_are_multiple(validator):
    clues = UNIQUE_CLUES[:3] + (
        CountClue("c4", B2, CountKind.AT_LEAST, 0, RowRegion(1)),
    )
    assert validator.check_uniqueness(BOARD, clues) is Uniqueness.MULTIPLE
    result = validator.validate(replace(PUZZLE, clues=clues))
    assert result.uniqueness is Uniqueness.MULTIPLE
    assert any("more than one" in error for error in result.errors)


def test_contradictory_clues_are_unsat(validator):
    clues = (
        UNIQUE_CLUES[0],
        CountClue("c2", B1, CountKind.EXACTLY, 0, RowRegion(0)),
    ) + UNIQUE_CLUES[2:]
    assert validator.check_uniqueness(BOARD, clues) is Uniqueness.UNSAT


def test_auxiliary_only_differences_are_not_extra_solutions(validator):
    clues = (
        CountClue("c1", A1, CountKind.AT_MOST, 1, RowRegion(0)),
        CountClue("c2", B1, CountKind.AT_LEAST, 1, RowRegion(0)),
        FactClue("c3", A2, A1, Status.INNOCENT),
        FactClue("c4", B2, A2, Status.INNOCENT),
        FactClue("c5", A1, B2, Status.INNOCENT),
    )
    assert validator.check_uniqueness(BOARD, clues) is Uniqueness.UNIQUE


def test_solution_that_breaks_a_clue_is_reported(validator):
    wrong = (Verdict(A1, Status.CRIMINAL),) + SOLUTION[1:]
    result = validator.validate(replace(PUZZLE, solution=wrong))
    assert result.uniqueness is None
    assert any("false for the stored solution" in error for error in result.errors)


@pytest.mark.parametrize(
    "change,message",
    [
        ({"initially_revealed": (Cell(5, 5),)}, "initially revealed"),
        ({"initially_revealed": (A1, A1)}, "initially revealed"),
        ({"solution": SOLUTION[:3]}, "every cell exactly one status"),
        ({"clues": UNIQUE_CLUES[:3]}, "exactly one clue"),
        ({"clues": UNIQUE_CLUES[:3] + (replace(UNIQUE_CLUES[3], id="c1"),)}, "ids"),
        (
            {"board": replace(BOARD, characters=BOARD.characters[::-1])},
            "row-major",
        ),
    ],
)
def test_malformed_puzzle_skips_uniqueness(validator, change, message):
    result = validator.validate(replace(PUZZLE, **change))
    assert result.uniqueness is None
    assert any(message in error for error in result.errors)


@pytest.mark.parametrize("path", PUZZLES, ids=lambda p: p.stem)
def test_shipped_puzzles_are_valid_and_unique(validator, path):
    result = validator.validate(JsonPuzzleLoader().load(path))
    assert result.errors == ()
    assert result.uniqueness is Uniqueness.UNIQUE
