from typing import List
from enum import Enum
from pydantic import BaseModel, Field

class HypothesisLabel(str, Enum):
    LIKELY = "LIKELY"
    POSSIBLE = "POSSIBLE"
    UNLIKELY = "UNLIKELY"

class Hypothesis(BaseModel):
    hypothesis_id: str
    description: str
    confidence: float
    supporting_evidence: List[str] = Field(default_factory=list)  # evidence IDs
    contradicting_evidence: List[str] = Field(default_factory=list)
    label: HypothesisLabel
