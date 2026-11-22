"""P4 trace records. Owner: Võ Tấn Lợi."""

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
    """One analysis, optionally followed by one submission; number starts at 1."""

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
