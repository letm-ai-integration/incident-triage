from typing import List
from pydantic import BaseModel, Field
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
