"""JSON loading contract. Puzzle data owner: Võ Tấn Lợi."""

from abc import ABC, abstractmethod
from pathlib import Path

from griductive.models import Puzzle


class PuzzleLoader(ABC):
    @abstractmethod
    def load(self, path: Path) -> Puzzle:
        """Read the JSON schema in docs/architecture.md into immutable records.

        Validate shape, ids, coordinates, enums, clue parameters, full solution
        and initial reveals. Raise ValueError for invalid content, OSError for
        I/O failures. Semantic/uniqueness checks belong to PuzzleValidator.
        """
        raise NotImplementedError
