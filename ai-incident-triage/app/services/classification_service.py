"""Graph-node adapter for ``deps["classification_service"]``.

Drop-in replacement for ``app.graph.nodes.classification._default_classify``
that uses the real LLM-backed Classification Agent (rules + LLM, see
app/agents/classification/agent.py) instead of the keyword-only fallback.
Returns the same state-update shape so no other node/router needs to change.
"""
from __future__ import annotations

from typing import Any

from app.agents.classification.agent import classify_incident
from app.domain.enums.status import IncidentStatus


def classification_service(state: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    incident = state["incident"]
    result = classify_incident(incident, model=deps.get("classification_model"))
    return {
        "classification": result,
        "incident_type": result.incident_type,
        "severity": result.priority,
        "classification_confidence": result.confidence,
        "investigation_status": IncidentStatus.TRIAGING,
    }
