"""Full-puzzle validation and uniqueness contract. Owner: Hồ Trần Quốc Thắng."""

from abc import ABC, abstractmethod

from griductive.encoder import CNFEncoder
from griductive.evaluator import ClueEvaluator
from griductive.models import (
    Board,
    Cell,
    Clue,
    Puzzle,
    SATStatus,
    Status,
    Uniqueness,
    ValidationResult,
)
from griductive.solver import SATSolver


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


class SATPuzzleValidator(PuzzleValidator):
    def __init__(
        self, encoder: CNFEncoder, solver: SATSolver, evaluator: ClueEvaluator
    ) -> None:
        self.encoder = encoder
        self.solver = solver
        self.evaluator = evaluator

    def check_uniqueness(self, board: Board, clues: tuple[Clue, ...]) -> Uniqueness:
        kb = self.encoder.encode(board, clues, ())
        first = self.solver.solve(kb.cnf, kb.variables)
        if first.status is SATStatus.UNSAT or first.model is None:
            return Uniqueness.UNSAT
        values = dict(first.model)
        primary = range(1, len(kb.variables.primary) + 1)
        blocking = tuple(-var if values[var] else var for var in primary)
        second = self.solver.solve(kb.cnf + (blocking,), kb.variables)
        if second.status is SATStatus.SAT:
            return Uniqueness.MULTIPLE
        return Uniqueness.UNIQUE

    def validate(self, puzzle: Puzzle) -> ValidationResult:
        errors = _structure_errors(puzzle)
        if errors:
            return ValidationResult(tuple(errors), None)

        board = puzzle.board
        solution = {verdict.cell: verdict.status for verdict in puzzle.solution}
        for clue in puzzle.clues:
            try:
                if not self.evaluator.evaluate(clue, solution, board):
                    errors.append(f"clue {clue.id}: false for the stored solution")
            except ValueError as exc:
                errors.append(f"clue {clue.id}: {exc}")
        if errors:
            return ValidationResult(tuple(errors), None)

        uniqueness = self.check_uniqueness(board, puzzle.clues)
        if uniqueness is Uniqueness.UNSAT:
            errors.append("the clues have no solution")
        elif uniqueness is Uniqueness.MULTIPLE:
            errors.append("the clues allow more than one solution")
        return ValidationResult(tuple(errors), uniqueness)


def _structure_errors(puzzle: Puzzle) -> list[str]:
    size = puzzle.board.size
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        return [f"board size must be a positive integer, got {size!r}"]
    cells = [Cell(row, col) for row in range(size) for col in range(size)]
    errors = []

    found = [character.cell for character in puzzle.board.characters]
    if found != cells:
        errors.append("characters must cover every cell once, in row-major order")
    names = [character.name.casefold() for character in puzzle.board.characters]
    if names != sorted(set(names)):
        errors.append("character names must be unique and alphabetical")

    owners = [clue.owner for clue in puzzle.clues]
    if sorted(owners) != cells:
        errors.append("every cell must own exactly one clue")
    ids = [clue.id for clue in puzzle.clues]
    if len(set(ids)) != len(ids) or not all(ids):
        errors.append("clue ids must be unique and non-empty")

    solved = [verdict.cell for verdict in puzzle.solution]
    if sorted(solved) != cells:
        errors.append("the solution must give every cell exactly one status")
    if not all(isinstance(v.status, Status) for v in puzzle.solution):
        errors.append("solution statuses must be CRIMINAL or INNOCENT")

    revealed = puzzle.initially_revealed
    outside = [cell for cell in revealed if cell not in cells]
    if outside or len(set(revealed)) != len(revealed):
        shown = ", ".join(str(cell) for cell in outside) or "duplicates"
        errors.append(f"initially revealed cells are invalid: {shown}")
    return errors
