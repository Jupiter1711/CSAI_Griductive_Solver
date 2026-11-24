"""Private game state and judge contract. Owner: Ngô Quang Minh."""

from abc import ABC, abstractmethod

from griductive.agent.inference import LogicAgent
from griductive.models import (
    Cell,
    Classification,
    PublicState,
    Puzzle,
    RunStatus,
    Status,
    SubmitResult,
    SubmitStatus,
    Uniqueness,
)
from griductive.regions import validate_cell
from griductive.validation import PuzzleValidator


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


class GridGameEngine(GameEngine):
    def __init__(self, validator: PuzzleValidator, judge: LogicAgent):
        self._validator = validator
        self._judge = judge
        self._puzzle: Puzzle | None = None
        self._state: PublicState | None = None

    @staticmethod
    def _snapshot(puzzle: Puzzle, revealed: set[Cell]) -> PublicState:
        verdicts = sorted(
            (v for v in puzzle.solution if v.cell in revealed), key=lambda v: v.cell
        )
        clues = sorted(
            (c for c in puzzle.clues if c.owner in revealed), key=lambda c: c.owner
        )
        return PublicState(puzzle.board, tuple(verdicts), tuple(clues))

    def load(self, puzzle: Puzzle) -> PublicState:
        result = self._validator.validate(puzzle)
        if result.errors or result.uniqueness is not Uniqueness.UNIQUE:
            raise ValueError(
                "; ".join(result.errors) or "puzzle must have one solution"
            )
        state = self._snapshot(puzzle, set(puzzle.initially_revealed))
        self._puzzle, self._state = puzzle, state
        return state

    def restart(self) -> PublicState:
        if self._puzzle is None:
            raise RuntimeError("no puzzle loaded")
        self._state = self._snapshot(self._puzzle, set(self._puzzle.initially_revealed))
        return self._state

    def public_state(self) -> PublicState:
        if self._state is None:
            raise RuntimeError("no puzzle loaded")
        return self._state

    def submit(self, cell: Cell, status: Status) -> SubmitResult:
        state = self.public_state()
        validate_cell(cell, state.board.size)
        if not isinstance(status, Status):
            raise ValueError("invalid verdict status")
        analysis = self._judge.classify(state)
        revealed = {v.cell for v in state.verdicts}
        clue = None
        if analysis.status is RunStatus.INCONSISTENT:
            outcome = SubmitStatus.INCONSISTENT
        elif cell in revealed:
            outcome = SubmitStatus.ALREADY_REVEALED
        else:
            classifications = {
                entry.cell: entry.classification for entry in analysis.cells
            }
            forced = classifications[cell]
            if forced is Classification.UNKNOWN:
                outcome = SubmitStatus.NOT_PROVABLE
            elif forced is not Classification(status.value):
                outcome = SubmitStatus.CONTRADICTED
            else:
                puzzle = self._puzzle
                assert puzzle is not None
                actual = next(v.status for v in puzzle.solution if v.cell == cell)
                if actual is not status:
                    raise ValueError("entailed verdict conflicts with puzzle solution")
                state = self._snapshot(puzzle, revealed | {cell})
                clue = next(c for c in state.clues if c.owner == cell)
                outcome = SubmitStatus.ACCEPTED
                self._state = state
        return SubmitResult(outcome, state, clue, analysis.kb, analysis.queries)
