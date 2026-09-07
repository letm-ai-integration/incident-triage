from typing import List

from pydantic import BaseModel, Field

from .claim_validation import ClaimValidationFinding
from .hypothesis import Hypothesis

class TimelineEvent(BaseModel):
    timestamp: str
    description: str

class RootCauseAnalysis(BaseModel):
    primary_cause: Hypothesis
    contributing_factors: List[Hypothesis] = Field(default_factory=list)
    confidence_score: float
    timeline: List[TimelineEvent] = Field(default_factory=list)
    affected_components: List[str] = Field(default_factory=list)
    # Phase 3: deterministic claim validation run before RCA finalization.
    # Populated by hypothesis_service.finalize_root_cause; the report/notification
    # must render these qualifiers instead of presenting downgraded claims as
    # confirmed facts.
    claim_validation: List[ClaimValidationFinding] = Field(default_factory=list)
