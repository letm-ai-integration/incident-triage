from enum import Enum

from pydantic import BaseModel, Field

from app.domain.enums.provenance import EvidenceProvenance


class HypothesisLabel(str, Enum):
    LIKELY = "LIKELY"
    POSSIBLE = "POSSIBLE"
    UNLIKELY = "UNLIKELY"

class Hypothesis(BaseModel):
    hypothesis_id: str
    description: str
    confidence: float
    supporting_evidence: list[str] = Field(default_factory=list)  # evidence IDs
    contradicting_evidence: list[str] = Field(default_factory=list)
    label: HypothesisLabel
    # Incident scoping: which incident this derived conclusion belongs to
    # (stamped by the orchestrator, mirroring Evidence.incident_id).
    incident_id: str | None = None
    # A hypothesis is by definition a derived conclusion (INFERRED). Runbook
    # matches are tagged CONTEXT to make clear they are guidance, not proof.
    provenance: EvidenceProvenance = EvidenceProvenance.INFERRED
