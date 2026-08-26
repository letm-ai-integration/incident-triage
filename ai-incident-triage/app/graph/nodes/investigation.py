# v2: runs the investigation stage.
#
# The node delegates the whole phase to the Investigation Orchestrator via
# ``deps["investigation_service"]`` (app/services/investigation_service.py),
# which executes app/agents/investigation/subgraph.py: three parallel
# sub-agents (log_analysis, kubernetes, runbook) aggregated into structured
# evidence/hypotheses written back into shared IncidentState. Findings are
# consolidated downstream by investigation_summary.
from __future__ import annotations

from typing import Optional

from langchain_core.runnables import RunnableConfig

from app.graph.builder import get_deps
from app.graph.state import IncidentState
from app.services.investigation_service import investigation_service as _default_service


def investigation_node(state: IncidentState, config: Optional[RunnableConfig] = None) -> dict:
    """Investigate the incident and write evidence + hypotheses to state."""
    deps = get_deps(config)
    service = deps.get("investigation_service", _default_service)
    try:
        update = service(state, deps)
    except Exception as exc:
        update = {"errors": state.get("errors", []) + [f"investigation failed: {exc}"]}
    update.setdefault("current_step", "investigation")
    return update
