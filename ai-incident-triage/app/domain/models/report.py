from datetime import datetime

from pydantic import BaseModel, Field

from .classification import ClassificationResult
from .evidence import EvidenceCollection
from .hypothesis import Hypothesis
from .root_cause import RootCauseAnalysis
from .verification import VerificationResult


class RunbookReference(BaseModel):
    runbook_id: str
    title: str
    url: str

class IncidentReport(BaseModel):
    incident_id: str
    classification: ClassificationResult
    evidence: EvidenceCollection
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    root_cause: RootCauseAnalysis
    recommended_actions: list[str] = Field(default_factory=list)
    runbook_references: list[RunbookReference] = Field(default_factory=list)
    verification: VerificationResult
    created_at: datetime
    report_version: int = 1
    # Incident-source facts carried for honest rendering (Phase 5): the report
    # must distinguish the *reported* narrative from independently *observed*
    # telemetry, so the original title/description/environment are kept on the
    # report instead of being reconstructed from downstream state.
    incident_title: str | None = None
    incident_description: str | None = None
    environment: str | None = None
