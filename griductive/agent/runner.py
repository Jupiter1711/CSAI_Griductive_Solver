"""P3 orchestration contract. Owner: Võ Tấn Lợi."""

from abc import ABC, abstractmethod

from griductive.agent.inference import LogicAgent
from griductive.agent.trace import DeductionStep, DeductionTrace
from griductive.engine import GameEngine
from griductive.models import (
    Classification,
    RunStatus,
    Status,
    SubmitStatus,
    Verdict
)


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


class GriductiveRunner(DeductionRunner):
    def step(self, engine: GameEngine, agent: LogicAgent, number: int) -> DeductionStep:
        state = engine.public_state()
        active_clue_ids = tuple(clue.id for clue in state.clues)
        
        analysis = agent.classify(state)
        
        if analysis.status != RunStatus.RUNNING:
            return DeductionStep(
                number=number,
                active_clue_ids=active_clue_ids,
                analysis=analysis,
                verdict=None,
                submission=None,
                state=state,
                status=analysis.status
            )
            
        forced_cell = None
        forced_status = None
        for cell_class in analysis.cells:
            if cell_class.classification != Classification.UNKNOWN:
                forced_cell = cell_class.cell
                forced_status = Status(cell_class.classification.value)
                break
                
        if forced_cell is None:
            return DeductionStep(
                number=number,
                active_clue_ids=active_clue_ids,
                analysis=analysis,
                verdict=None,
                submission=None,
                state=state,
                status=RunStatus.STUCK
            )

        verdict = Verdict(cell=forced_cell, status=forced_status)
        submission = engine.submit(cell=forced_cell, status=forced_status)
        
        if submission.status != SubmitStatus.ACCEPTED:
            raise RuntimeError(f"Engine bất ngờ từ chối verdict: {submission.status.name}")
            
        new_state = submission.state
        
        is_solved = len(new_state.verdicts) == (new_state.board.size * new_state.board.size)
        final_status = RunStatus.SOLVED if is_solved else RunStatus.RUNNING
        
        return DeductionStep(
            number=number,
            active_clue_ids=active_clue_ids,
            analysis=analysis,
            verdict=verdict,
            submission=submission,
            state=new_state,
            status=final_status
        )

    def run(self, engine: GameEngine, agent: LogicAgent) -> DeductionTrace:
        steps = []
        number = 1
        
        while True:
            current_step = self.step(engine, agent, number)
            steps.append(current_step)
            
            if current_step.status != RunStatus.RUNNING:
                break
            
            number += 1
            
        return DeductionTrace(
            steps=tuple(steps),
            final_state=steps[-1].state,
            status=steps[-1].status
        )
