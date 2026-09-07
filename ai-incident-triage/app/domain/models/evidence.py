from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums.provenance import EvidenceProvenance


class Evidence(BaseModel):
    evidence_id: str
    source: str  # e.g., "log_analysis", "runbook", "kubernetes"
    finding: str
    severity: str
    raw_data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None
    # Incident scoping: every piece of evidence is attributable to exactly one
    # incident (id + environment). The orchestrator stamps these on every item
    # so no claim can leak between incidents/services/time windows downstream.
    incident_id: str | None = None
    environment: str | None = None
    # Grounding model: where this finding actually came from. The conservative
    # default is REPORTED (unverified); producers must raise it to OBSERVED
    # only when the telemetry they quote was genuinely available.
    provenance: EvidenceProvenance = EvidenceProvenance.REPORTED

class EvidenceCollection(BaseModel):
    items: list[Evidence] = Field(default_factory=list)
    summary: str
