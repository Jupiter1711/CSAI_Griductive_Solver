"""Direct semantics contract. Owner: Ngô Quang Minh."""

from abc import ABC, abstractmethod
from collections.abc import Mapping

from griductive.models import (
    BinaryClue,
    BinaryKind,
    Board,
    Cell,
    Clue,
    CountClue,
    CountKind,
    FactClue,
    Status,
)
from griductive.regions import GridRegionResolver, validate_cell


class ClueEvaluator(ABC):
    @abstractmethod
    def evaluate(
        self, clue: Clue, assignment: Mapping[Cell, Status], board: Board
    ) -> bool:
        """Evaluate a clue directly, without calling the encoder or SAT solver.

        Require a complete board assignment. Invalid references, parameters or
        missing/extra assignment cells raise ValueError, not False.
        """
        raise NotImplementedError


class DirectClueEvaluator(ClueEvaluator):
    def evaluate(
        self, clue: Clue, assignment: Mapping[Cell, Status], board: Board
    ) -> bool:
        size = board.size
        if type(size) is not int or size < 1:
            raise ValueError("invalid board size")
        if not isinstance(assignment, Mapping) or len(assignment) != size * size:
            raise ValueError("expected one status per board cell")
        for cell, status in assignment.items():
            validate_cell(cell, size)
            if not isinstance(status, Status):
                raise ValueError(f"invalid assignment status at {cell!r}")
        if not isinstance(clue, (FactClue, BinaryClue, CountClue)):
            raise ValueError("unknown clue type")
        validate_cell(clue.owner, size)
        if isinstance(clue, FactClue):
            if not isinstance(clue.status, Status):
                raise ValueError("invalid FACT status")
            return assignment[validate_cell(clue.target, size)] is clue.status
        if isinstance(clue, BinaryClue):
            if not isinstance(clue.kind, BinaryKind):
                raise ValueError("invalid binary clue kind")
            left = assignment[validate_cell(clue.left, size)]
            right = assignment[validate_cell(clue.right, size)]
            return left == right if clue.kind is BinaryKind.SAME else left != right

        cells = GridRegionResolver().resolve(clue.region, board)
        if type(clue.k) is not int or not 0 <= clue.k <= len(cells):
            raise ValueError("k must be an integer between zero and the region size")
        count = sum(assignment[cell] is Status.CRIMINAL for cell in cells)
        if clue.kind is CountKind.EXACTLY:
            return count == clue.k
        if clue.kind is CountKind.AT_LEAST:
            return count >= clue.k
        if clue.kind is CountKind.AT_MOST:
            return count <= clue.k
        raise ValueError("invalid counting clue kind")
