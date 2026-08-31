# Shared LangGraph state.
#
# v2 pipeline: ingestion -> classification (category + severity) ->
# investigation (parallel sub-agents) -> investigation_summary -> rca_report ->
# approval -> verification -> notification.
#
# This is the single canonical graph-state shape. Every field is declared here;
# nodes only ever return keys declared on this TypedDict. Where a concept has an
# existing domain model or enum, the field references it directly instead of
# re-declaring a parallel inline definition.
from dataclasses import dataclass
from enum import Enum
from typing import Optional, TypedDict

from app.domain.enums.incident_type import IncidentType
from app.domain.enums.priority import Priority
from app.domain.enums.status import ApprovalStatus, IncidentStatus, NotificationStatus
from app.domain.models.approval import ApprovalDecision
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis
from app.domain.models.incident import Incident
from app.domain.models.report import IncidentReport
from app.domain.models.root_cause import RootCauseAnalysis
from app.domain.models.verification import VerificationResult


class RunbookStatus(str, Enum):
    MATCHED = "MATCHED"
    NO_MATCH = "NO_MATCH"
    ERROR = "ERROR"


@dataclass
class RunbookResult:
    status: RunbookStatus
    hypothesis: Optional["Hypothesis"] = None
    error: str | None = None
    matched_title: str | None = None
    score: float | None = None


class IncidentState(TypedDict, total=False):

    # 1. Incident Input
    incident_id: str
    incident: Incident
    raw_input: dict
    normalized_input: dict

    # 2. Classification
    classification: ClassificationResult
    incident_type: IncidentType
    severity: Priority
    classification_confidence: float

    # 3. Investigation
    investigation_status: IncidentStatus
    evidence: list[Evidence]
    hypotheses: list[Hypothesis]

    # Parallel Investigation Results
    log_analysis: Evidence
    runbook_analysis: Evidence
    kubernetes_analysis: Evidence

    # 4. Investigation Summary
    investigation_summary: dict

    # 5. RCA & Report
    root_cause: RootCauseAnalysis
    rca_confidence: float
    incident_report: IncidentReport

    # 6. Verification
    expected_outcome: dict
    verification_result: VerificationResult
    is_resolved: bool

    # 7. Workflow Control
    retry_count: int
    current_step: str
    errors: list[str]

    # 8. Approval
    approval: ApprovalDecision
    approval_status: ApprovalStatus

    # 9. Notification
    notification_status: NotificationStatus

    # 10. Guardrails
    # Accumulated (never overwritten) findings from every step guardrail that
    # ran and failed, across every node -- see app/guardrails/.
    guardrail_findings: list[dict]
