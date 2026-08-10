"""Notification node: send final report notifications."""

from __future__ import annotations

from app.dependencies import get_dependencies
from app.schemas.graph_state import IncidentTriageState


async def notification_node(state: IncidentTriageState) -> dict:
    report = state.get("rca_report")
    if report is None:
        return {"notification": ""}
    deps = get_dependencies()
    message = await deps.notification_agent.run(report)
    return {"notification": message}
