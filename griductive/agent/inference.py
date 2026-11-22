"""P1/P2 contract. Owner: Nguyễn Lê Khánh Toàn."""

from abc import ABC, abstractmethod

from griductive.models import ClassificationResult, EncodedKB, PublicState


class LogicAgent(ABC):
    @abstractmethod
    def build_kb(self, state: PublicState) -> EncodedKB:
        """Use CNFEncoder on exactly state.clues and state.verdicts.

        No access to Puzzle, GameEngine, hidden solution or unrevealed clues.
        Malformed public input raises ValueError.
        """
        raise NotImplementedError

    @abstractmethod
    def classify(self, state: PublicState) -> ClassificationResult:
        """Build KB; check SAT before testing both signs of each unresolved cell.

        Return INCONSISTENT with no classifications if KB is UNSAT. Otherwise
        return every unresolved cell in row-major order, with UNKNOWN if both
        assumptions are SAT. Status is SOLVED if no cells remain, STUCK if all
        are unknown, otherwise RUNNING. Include every SAT query and its stats.
        This read-only operation also supplies hints without revealing a card.
        """
        raise NotImplementedError
