"""P3 orchestration contract. Owner: Võ Tấn Lợi."""

from abc import ABC, abstractmethod

from griductive.agent.inference import LogicAgent
from griductive.agent.trace import DeductionStep, DeductionTrace
from griductive.engine import GameEngine


class DeductionRunner(ABC):
    @abstractmethod
    def step(self, engine: GameEngine, agent: LogicAgent, number: int) -> DeductionStep:
        """Classify public_state and submit the first forced cell in row-major.

        number must be positive. On terminal analysis, do not submit. After
        acceptance, capture the revealed clue via SubmitResult and fresh state;
        report SOLVED if all cards are revealed, otherwise RUNNING. Unexpected
        rejection raises RuntimeError rather than looping forever. Only the
        public snapshot may cross the inference boundary.
        """
        raise NotImplementedError

    @abstractmethod
    def run(self, engine: GameEngine, agent: LogicAgent) -> DeductionTrace:
        """Repeat step from 1 until SOLVED, STUCK or INCONSISTENT; never guess.

        Include the final terminal analysis even if it submits no verdict.
        Do not restart/load the engine implicitly.
        """
        raise NotImplementedError
