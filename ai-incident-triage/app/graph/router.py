"""Conditional routing for the AI Incident Triage v2 workflow.

The router determines *which* route to take; the graph builder connects the
returned route keys to graph nodes. Business rules that decide routing belong
here — not in the builder.
"""

from __future__ import annotations

from app.schemas.graph_state import IncidentTriageState


def route_after_verification(state: IncidentTriageState) -> str:
    """Route resolved incidents to notification, unresolved back to investigation.

    Returns ``"notification"`` when the verification node reported the incident
    resolved, otherwise ``"investigation"`` to trigger a re-investigation loop.
    """
    verification = state.get("verification")
    resolved = False
    if verification is not None:
        resolved = (
            verification.get("resolved")
            if isinstance(verification, dict)
            else verification.resolved
        )
    if resolved:
        return "notification"
    return "investigation"
