from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from .classification import ClassificationResult
from .evidence import EvidenceCollection
from .hypothesis import Hypothesis
from .root_cause import RootCauseAnalysis
from .verification import VerificationResult
from .approval import ApprovalDecision

class RunbookReference(BaseModel):
    runbook_id: str
    title: str
    url: str

class IncidentReport(BaseModel):
    incident_id: str
    classification: ClassificationResult
    evidence: EvidenceCollection
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    root_cause: RootCauseAnalysis
    recommended_actions: List[str] = Field(default_factory=list)
    runbook_references: List[RunbookReference] = Field(default_factory=list)
    verification: VerificationResult
    approval: Optional[ApprovalDecision] = None
    created_at: datetime
    report_version: int = 1
