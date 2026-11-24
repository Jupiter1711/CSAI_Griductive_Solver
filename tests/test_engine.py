from dataclasses import replace
from unittest.mock import create_autospec

import pytest

from griductive.agent.inference import LogicAgent
from griductive.engine import GridGameEngine
from griductive.models import (
    Board,
    Cell,
    CellClassification,
    Character,
    Classification,
    ClassificationResult,
    EncodedKB,
    FactClue,
    Puzzle,
    RunStatus,
    Status,
    SubmitStatus,
    Uniqueness,
    ValidationResult,
    VarMap,
    Verdict,
)
from griductive.validation import PuzzleValidator


@pytest.fixture
def game():
    cells = tuple(Cell(r, c) for r in range(3) for c in range(3))
    board = Board(3, tuple(Character(c, str(i), "artist") for i, c in enumerate(cells)))
    verdicts = tuple(Verdict(c, Status.CRIMINAL) for c in cells)
    clues = tuple(
        FactClue(str(i), c, cells[(i + 1) % 9], Status.CRIMINAL)
        for i, c in enumerate(cells)
    )
    puzzle = Puzzle("chain", board, clues, verdicts, (cells[0],))
    validator = create_autospec(PuzzleValidator, instance=True)
    validator.validate.return_value = ValidationResult((), Uniqueness.UNIQUE)
    judge = create_autospec(LogicAgent, instance=True)
    analysis = ClassificationResult(
        RunStatus.RUNNING,
        EncodedKB((), VarMap(cells)),
        tuple(
            CellClassification(
                c, Classification.CRIMINAL if i == 1 else Classification.UNKNOWN
            )
            for i, c in enumerate(cells)
            if i
        ),
        (),
    )
    judge.classify.return_value = analysis
    return GridGameEngine(validator, judge), puzzle, judge, validator


def test_reveal_only_after_proof_and_restart(game):
    engine, puzzle, judge, _ = game
    initial = engine.load(puzzle)
    assert initial.clues == puzzle.clues[:1]
    assert initial.verdicts == puzzle.solution[:1]
    target = puzzle.clues[1].owner
    for cell, status, outcome in [
        (puzzle.clues[2].owner, Status.CRIMINAL, SubmitStatus.NOT_PROVABLE),
        (target, Status.INNOCENT, SubmitStatus.CONTRADICTED),
        (puzzle.clues[0].owner, Status.CRIMINAL, SubmitStatus.ALREADY_REVEALED),
    ]:
        rejected = engine.submit(cell, status)
        assert rejected.status is outcome and rejected.revealed_clue is None
        assert engine.public_state() == rejected.state == initial
    accepted = engine.submit(target, Status.CRIMINAL)
    judge.classify.assert_called_with(initial)
    assert accepted.status is SubmitStatus.ACCEPTED
    assert accepted.revealed_clue == puzzle.clues[1]
    assert accepted.state.clues == puzzle.clues[:2]
    assert accepted.state.verdicts == puzzle.solution[:2]
    assert engine.restart() == initial


def test_atomic_failures(game):
    engine, puzzle, judge, validator = game
    with pytest.raises(RuntimeError):
        engine.submit(Cell(0, 0), Status.INNOCENT)
    state = engine.load(puzzle)
    validator.validate.return_value = ValidationResult((), Uniqueness.MULTIPLE)
    with pytest.raises(ValueError):
        engine.load(replace(puzzle, id="invalid"))
    assert engine.public_state() == state
    target = puzzle.solution[1].cell
    analysis = judge.classify.return_value
    judge.classify.return_value = replace(
        analysis, status=RunStatus.INCONSISTENT, cells=()
    )
    result = engine.submit(target, Status.CRIMINAL)
    assert result.status is SubmitStatus.INCONSISTENT and result.revealed_clue is None
    judge.classify.return_value = replace(
        analysis, cells=(CellClassification(target, Classification.INNOCENT),)
    )
    with pytest.raises(ValueError, match="conflicts"):
        engine.submit(target, Status.INNOCENT)
    assert engine.public_state() == state
