"""Verification node: compare with mock outcome, resolved vs. unresolved."""

from __future__ import annotations

from app.dependencies import get_dependencies
from app.schemas.graph_state import IncidentTriageState


async def verification_node(state: IncidentTriageState) -> dict:
    incident = state.get("incident")
    if incident is None:
        return {"verification": None}
    deps = get_dependencies()
    verification = deps.verification_service.verify(incident)
    return {"verification": verification}
