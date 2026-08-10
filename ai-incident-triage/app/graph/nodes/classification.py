"""Classification node: emit incident category AND severity (P1/P2/P3).

v2 merges the former v1 severity node into classification.
"""

from __future__ import annotations

from app.dependencies import get_dependencies
from app.schemas.graph_state import IncidentTriageState


async def classification_node(state: IncidentTriageState) -> dict:
    incident = state.get("incident")
    if incident is None:
        return {"classification": None}
    deps = get_dependencies()
    classification = await deps.classification_agent.run(incident)
    return {"classification": classification}
