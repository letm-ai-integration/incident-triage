# Shared LangGraph state. v2 fields: incident, classification (incl. severity), investigation_summary, rca_report, approval, verification, notification.
from typing import TypedDict, List, Optional


class IncidentState(TypedDict, total=False):

    # 1. Incident Input
    incident_id: str
    raw_input: dict
    normalized_input: dict

    # 2. Classification
    incident_type: str
    severity: str
    classification_confidence: float

    # 3. Investigation
    investigation_status: str
    evidence: List[dict]
    hypotheses: List[dict]

    # Parallel Investigation Results
    log_analysis: dict
    runbook_analysis: dict
    kubernetes_analysis: dict

    # 4. Investigation Summary
    investigation_summary: dict

    # 5. RCA & Report
    root_cause: dict
    rca_confidence: float
    incident_report: dict

    # 6. Verification
    expected_outcome: dict
    verification_result: dict
    is_resolved: bool

    # 7. Workflow Control
    retry_count: int
    current_step: str
    errors: List[str]

    # 8. Approval
    approval_status: str

    # 9. Notification
    notification_status: str