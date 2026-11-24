from griductive.agent.inference import LogicAgent
from griductive.agent.runner import DeductionRunner
from griductive.agent.trace import DeductionStep, DeductionTrace
from griductive.engine import GameEngine
from griductive.models import (
    Classification,
    RunStatus,
    Status,
    SubmitStatus,
    Verdict
)

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