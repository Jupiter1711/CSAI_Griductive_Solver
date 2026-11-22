"""Full-puzzle validation and uniqueness contract. Owner: unassigned."""

from abc import ABC, abstractmethod

from griductive.models import Board, Clue, Puzzle, Uniqueness, ValidationResult


class PuzzleValidator(ABC):
    @abstractmethod
    def check_uniqueness(self, board: Board, clues: tuple[Clue, ...]) -> Uniqueness:
        """Check all clues without adding the supplied solution as unit clauses.

        Find a model, then block only its primary assignment and solve again.
        Auxiliary-only differences are not distinct puzzle solutions.
        Invalid data raises ValueError. UNSAT, UNIQUE and MULTIPLE are distinct.
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, puzzle: Puzzle) -> ValidationResult:
        """Check structure, evaluate every clue on solution, and check uniqueness.

        Return diagnostic errors; uniqueness=None when malformed data prevents
        checking. No errors and UNIQUE means valid. Uniqueness alone does not
        guarantee progressive no-guess play can finish. Never expose this
        full-clue validation state to LogicAgent.
        """
        raise NotImplementedError
