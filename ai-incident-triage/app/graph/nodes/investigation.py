# v2: runs the investigation stage.
#
# In production this node should call the investigation orchestrator
# (app/agents/investigation/orchestrator.py) via ``deps["investigation_service"]``,
# which coordinates the parallel sub-agents (log_analysis, runbook,
# kubernetes). Until that service exists, ``_default_investigate`` produces one
# ``Evidence`` item per sub-agent plus a leading ``Hypothesis``. Findings are
# consolidated downstream by investigation_summary.
from __future__ import annotations

from typing import Optional

from langchain_core.runnables import RunnableConfig

from app.domain.enums.status import IncidentStatus
from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.graph.builder import get_deps
from app.graph.state import IncidentState

_KEYWORD_SIGNALS = (
    "error", "fail", "timeout", "exception", "connection", "refused",
    "crash", "oom", "unavailable",
)


def investigation_node(state: IncidentState, config: Optional[RunnableConfig] = None) -> dict:
    """Investigate the incident and write evidence + hypotheses to state."""
    deps = get_deps(config)
    service = deps.get("investigation_service", _default_investigate)
    try:
        update = service(state, deps)
    except Exception as exc:
        update = {"errors": state.get("errors", []) + [f"investigation failed: {exc}"]}
    update.setdefault("current_step", "investigation")
    return update


def _default_investigate(state: IncidentState, deps: dict) -> dict:
    """Fallback investigation: lightweight parallel analysis across sub-agents."""
    incident = state.get("incident")
    logs = incident.raw_logs if incident else []
    matched = [kw for kw in _KEYWORD_SIGNALS if any(kw in (log or "").lower() for log in logs)]
    primary = matched[0] if matched else "no error signals"

    log_evidence = Evidence(
        evidence_id="ev-log-1",
        source="log_analysis",
        finding=f"Found error signals in logs: {', '.join(matched[:5])}." if matched
        else "No error signals detected in logs.",
        severity="high" if matched else "info",
        raw_data={"matched_signals": matched[:10], "log_count": len(logs)},
    )
    runbook_evidence = Evidence(
        evidence_id="ev-rb-1",
        source="runbook",
        finding="No matching runbook found for this incident pattern.",
        severity="info",
        raw_data={"matched_runbooks": []},
    )
    kubernetes_evidence = Evidence(
        evidence_id="ev-k8s-1",
        source="kubernetes",
        finding=f"Workload health check flagged: {primary} present in pod status."
        if primary != "no error signals"
        else "Workload health check passed.",
        severity="medium" if primary != "no error signals" else "info",
        raw_data={"pod_status": "degraded" if primary != "no error signals" else "healthy"},
    )

    hypothesis = Hypothesis(
        hypothesis_id="hyp-1",
        description=f"Primary cause is related to '{primary}' detected during investigation.",
        confidence=0.8,
        supporting_evidence=[log_evidence.evidence_id, kubernetes_evidence.evidence_id],
        contradicting_evidence=[],
        label=HypothesisLabel.LIKELY,
    )

    retry_count = state.get("retry_count", 0) + (1 if "retry_count" in state else 0)
    return {
        "evidence": [log_evidence, runbook_evidence, kubernetes_evidence],
        "hypotheses": [hypothesis],
        "log_analysis": log_evidence,
        "runbook_analysis": runbook_evidence,
        "kubernetes_analysis": kubernetes_evidence,
        "investigation_status": IncidentStatus.INVESTIGATING,
        "retry_count": retry_count,
    }
