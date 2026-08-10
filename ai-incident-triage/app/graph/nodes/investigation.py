"""Investigation node: orchestrate parallel investigation sub-agents.

v2: log_analysis, runbook, kubernetes sub-agents run in parallel; findings are
consolidated by the investigation_summary node.
"""

from __future__ import annotations

from app.dependencies import get_dependencies
from app.schemas.graph_state import IncidentTriageState


async def investigation_node(state: IncidentTriageState) -> dict:
    incident = state.get("incident")
    if incident is None:
        return {"investigation_summary": None}
    deps = get_dependencies()
    summary = await deps.investigation_orchestrator.run(incident)
    return {"investigation_summary": summary}
