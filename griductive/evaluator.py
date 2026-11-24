"""Direct semantics contract. Owner: Ngô Quang Minh."""

from abc import ABC, abstractmethod
from collections.abc import Mapping

from griductive.models import (
    BinaryClue,
    BinaryKind,
    Board,
    Cell,
    Clue,
    CountKind,
    FactClue,
    IntersectionClue,
    ParityClue,
    ParityKind,
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
        if not isinstance(clue, Clue):
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

        resolver = GridRegionResolver()
        if isinstance(clue, IntersectionClue):
            if not isinstance(clue.regions, tuple) or not clue.regions:
                raise ValueError("intersection requires at least one region")
            first, *rest = clue.regions
            cells = set(resolver.resolve(first, board))
            for region in rest:
                cells.intersection_update(resolver.resolve(region, board))
        else:
            cells = resolver.resolve(clue.region, board)

        count = sum(assignment[cell] is Status.CRIMINAL for cell in cells)
        if isinstance(clue, ParityClue):
            if not isinstance(clue.kind, ParityKind):
                raise ValueError("invalid parity kind")
            return count % 2 == (1 if clue.kind is ParityKind.ODD else 0)

        if type(clue.k) is not int or not 0 <= clue.k <= len(cells):
            raise ValueError("k must be an integer between zero and the region size")
        if isinstance(clue, IntersectionClue) or clue.kind is CountKind.EXACTLY:
            return count == clue.k
        if clue.kind is CountKind.AT_LEAST:
            return count >= clue.k
        if clue.kind is CountKind.AT_MOST:
            return count <= clue.k
        raise ValueError("invalid counting clue kind")
