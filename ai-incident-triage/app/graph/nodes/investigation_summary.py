"""Investigation summary node: consolidate evidence + hypotheses.

v2: the orchestrator already consolidates sub-agent findings; this node
normalizes the summary into the graph state contract.
"""

from __future__ import annotations

from app.schemas.graph_state import IncidentTriageState


async def investigation_summary_node(state: IncidentTriageState) -> dict:
    summary = state.get("investigation_summary")
    return {"investigation_summary": summary}
