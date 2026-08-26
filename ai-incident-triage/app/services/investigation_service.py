"""Graph-node adapter for ``deps["investigation_service"]``.

Drop-in replacement for ``app.graph.nodes.investigation._default_investigate``
that fans out to the real Log Analysis, Kubernetes, and Runbook sub-agents via
``app.agents.investigation.orchestrator`` instead of local keyword matching.
Returns the same state-update shape so no other node/router needs to change.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.agents.investigation.orchestrator import run_investigation
from app.domain.enums.status import IncidentStatus


def investigation_service(state: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    incident = state["incident"]
    classification = state.get("classification")
    outcome = asyncio.run(
        run_investigation(
            incident,
            classification,
            log_analysis_model=deps.get("log_analysis_model"),
            kubernetes_model=deps.get("kubernetes_model"),
        )
    )
    retry_count = state.get("retry_count", 0) + (1 if "retry_count" in state else 0)
    return {
        "evidence": outcome.evidence,
        "hypotheses": outcome.hypotheses,
        "log_analysis": outcome.log_analysis,
        "runbook_analysis": outcome.runbook_analysis,
        "kubernetes_analysis": outcome.kubernetes_analysis,
        "investigation_status": IncidentStatus.INVESTIGATING,
        "retry_count": retry_count,
    }
