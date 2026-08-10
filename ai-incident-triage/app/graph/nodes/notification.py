# v2: terminal notification stage. Both the success and rejection paths converge
# here. In production this delegates to the notification agent via
# ``deps["notification_service"]`` (app/agents/notification/agent.py).
from __future__ import annotations

from typing import Optional

from langchain_core.runnables import RunnableConfig

from app.domain.enums.status import IncidentStatus, NotificationStatus
from app.graph.builder import get_deps
from app.graph.state import IncidentState


def notification_node(state: IncidentState, config: Optional[RunnableConfig] = None) -> dict:
    """Notify stakeholders and record the terminal notification status."""
    deps = get_deps(config)
    service = deps.get("notification_service", _default_notify)
    try:
        update = service(state, deps)
    except Exception as exc:
        update = {
            "notification_status": NotificationStatus.FAILED,
            "errors": state.get("errors", []) + [f"notification failed: {exc}"],
        }
    update.setdefault("current_step", "notification")
    return update


def _default_notify(state: IncidentState, deps: dict) -> dict:
    """Fallback notification: mark stakeholders notified with the final status."""
    verification = state.get("verification_result")
    if verification is not None:
        status = IncidentStatus.RESOLVED if verification.is_resolved else IncidentStatus.UNRESOLVED
    else:
        # No verification ran (auto-resolve path): the incident was closed
        # directly after triage.
        status = IncidentStatus.CLOSED
    return {
        "notification_status": NotificationStatus.NOTIFIED,
        "investigation_status": status,
    }
