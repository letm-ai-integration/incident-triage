"""RCA report node: determine root cause + confidence and generate the report.

v2: merges the former v1 rca and report nodes.
"""

from __future__ import annotations

from app.dependencies import get_dependencies
from app.schemas.graph_state import IncidentTriageState


async def rca_report_node(state: IncidentTriageState) -> dict:
    incident = state.get("incident")
    summary = state.get("investigation_summary")
    if incident is None or summary is None:
        return {"rca_report": None}
    deps = get_dependencies()
    report = await deps.rca_report_agent.run(incident, summary)
    return {"rca_report": report}
