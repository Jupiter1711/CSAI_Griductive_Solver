from dataclasses import dataclass
from griductive.models import (
    ClassificationResult,
    PublicState,
    RunStatus,
    SubmitResult,
    Verdict,
)

@dataclass(frozen=True)
class DeductionStep:
    number: int
    active_clue_ids: tuple[str, ...]
    analysis: ClassificationResult
    verdict: Verdict | None
    submission: SubmitResult | None
    state: PublicState
    status: RunStatus

@dataclass(frozen=True)
class DeductionTrace:
    steps: tuple[DeductionStep, ...]
    final_state: PublicState
    status: RunStatus