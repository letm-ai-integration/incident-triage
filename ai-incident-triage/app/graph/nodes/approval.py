"""Approval node: human-in-the-loop approval using a LangGraph interrupt.

The node pauses the graph and surfaces an approval request. On resume it
records the human decision. Framework control-flow (interrupt/resume) must be
preserved — this node never catches exceptions.
"""

from __future__ import annotations

from langgraph.types import interrupt

from app.dependencies import get_dependencies
from app.schemas.graph_state import IncidentTriageState


async def approval_node(state: IncidentTriageState) -> dict:
    report = state.get("rca_report")
    payload = {
        "prompt": f"Approve RCA report: {report.title if report else 'unknown'}",
    }
    decision = interrupt(payload)
    deps = get_dependencies()
    approved = bool(decision and decision.get("approved", False))
    approval = deps.approval_service.record(
        approved=approved,
        reviewer=str(decision.get("reviewer", "")) if decision else "",
        comments=str(decision.get("comments", "")) if decision else "",
    )
    return {"approval": approval}
