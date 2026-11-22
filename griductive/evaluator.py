"""Direct semantics contract. Owner: Ngô Quang Minh."""

from abc import ABC, abstractmethod
from collections.abc import Mapping

from griductive.models import Board, Cell, Clue, Status


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
