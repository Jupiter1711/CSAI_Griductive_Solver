"""Private game state and judge contract. Owner: Ngô Quang Minh."""

from abc import ABC, abstractmethod

from griductive.models import Cell, PublicState, Puzzle, Status, SubmitResult


class GameEngine(ABC):
    @abstractmethod
    def load(self, puzzle: Puzzle) -> PublicState:
        """Validate then atomically replace the puzzle; failure preserves old state.

        Invalid puzzles raise ValueError. Initially reveal only the supplied
        initial cards. Full validation must use PuzzleValidator before play.
        """
        raise NotImplementedError

    @abstractmethod
    def restart(self) -> PublicState:
        """Restore initial reveals. Raise RuntimeError if no puzzle is loaded."""
        raise NotImplementedError

    @abstractmethod
    def public_state(self) -> PublicState:
        """Return an immutable public snapshot, never Puzzle or private references.

        Raise RuntimeError if no puzzle is loaded.
        """
        raise NotImplementedError

    @abstractmethod
    def submit(self, cell: Cell, status: Status) -> SubmitResult:
        """Judge using only current public KB, checking consistency first.

        ACCEPTED adds the verdict and reveals its clue atomically. All other
        outcomes preserve state and return revealed_clue=None. Matching the
        secret solution alone is insufficient. An entailed verdict conflicting
        with the stored solution raises ValueError without mutation.
        Invalid cell/status raises ValueError; no puzzle raises RuntimeError.
        Record judge SAT calls separately from the agent's calls.
        """
        raise NotImplementedError
