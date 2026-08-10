# v2: human sign-off gate.
#
# Routes to verification when approved and to the rejection notification when
# not (see router.route_after_approval). Production approval policy lives in
# app/rules/ (ownership.py, confidence.py) and would be wrapped by
# ``deps["approval_service"]``; until then ``_default_approve`` applies a small
# inline policy (P1/P2 or low confidence requires sign-off).
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from langchain_core.runnables import RunnableConfig

from app.domain.constants import DEFAULT_CONFIDENCE_SCORE
from app.domain.enums.priority import Priority
from app.domain.enums.status import ApprovalStatus
from app.domain.models.approval import ApprovalDecision
from app.graph.builder import get_deps
from app.graph.state import IncidentState


def approval_node(state: IncidentState, config: Optional[RunnableConfig] = None) -> dict:
    """Record the approval decision and its status in state."""
    deps = get_deps(config)
    service = deps.get("approval_service", _default_approve)
    try:
        update = service(state, deps)
    except Exception as exc:
        update = {"errors": state.get("errors", []) + [f"approval failed: {exc}"]}
    update.setdefault("current_step", "approval")
    return update


def _default_approve(state: IncidentState, deps: dict) -> dict:
    """Fallback approval: auto-approve unless policy requires human sign-off."""
    classification = state.get("classification")
    priority = (
        classification.priority if classification else (state.get("severity") or Priority.P3)
    )
    confidence = (
        classification.confidence
        if classification
        else state.get("classification_confidence", DEFAULT_CONFIDENCE_SCORE)
    )
    auto_approve = bool(deps.get("auto_approve", True))
    requires_approval = priority in (Priority.P1, Priority.P2) or confidence < DEFAULT_CONFIDENCE_SCORE

    if not requires_approval or auto_approve:
        decision = ApprovalDecision(
            approved=True,
            reviewer="system",
            comments="Auto-approved: policy sign-off not required or auto-approve enabled.",
            timestamp=datetime.now(timezone.utc),
        )
        status = ApprovalStatus.APPROVED
    else:
        decision = ApprovalDecision(
            approved=False,
            reviewer="",
            comments="Human approval required and no reviewer is available; rejected.",
            timestamp=datetime.now(timezone.utc),
        )
        status = ApprovalStatus.REJECTED

    update: dict = {"approval": decision, "approval_status": status}
    report = state.get("incident_report")
    if report is not None:
        update["incident_report"] = report.model_copy(update={"approval": decision})
    return update
