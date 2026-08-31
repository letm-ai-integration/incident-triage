"""Graph-node adapter for ``deps["investigation_service"]``.

Default investigation implementation for the graph's ``investigation`` node:
runs the real Investigation Orchestrator (log analysis + Kubernetes + runbook
sub-agents, see app/agents/investigation/subgraph.py). Works with or without
an LLM: without one the orchestrator's deterministic fallbacks are used, so
this service is safe to inject unconditionally.

Returns the same state-update shape as the node's fallback, including the
per-source evidence fields (``log_analysis`` / ``kubernetes_analysis`` /
``runbook_analysis``) downstream nodes and tests rely on.
"""
from __future__ import annotations

from typing import Any

from app.agents.investigation.orchestrator import investigate
from app.domain.enums.status import IncidentStatus
from app.llm.client import LLMConfigurationError, get_chat_model
from app.logging_utils import agent_entry, agent_output, agent_exit, agent_error


def investigation_service(state: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    incident = state["incident"]
    classification = state.get("classification")

    agent_entry("InvestigationService", f"incident={incident.incident_id}")

    llm = None
    if deps.get("use_llm"):
        try:
            llm = deps.get("investigation_llm") or get_chat_model()
        except LLMConfigurationError:
            llm = None  # fall back to deterministic sub-agent analysis

    try:
        outcome = investigate(incident, classification, llm=llm)
        agent_output(
            "InvestigationService",
            f"confidence={outcome.confidence:.2f} evidence={len(outcome.evidence)}",
        )
    except Exception as exc:
        agent_error("InvestigationService", exc)
        raise
    finally:
        agent_exit("InvestigationService")

    retry_count = state.get("retry_count", 0) + (1 if "retry_count" in state else 0)
    return {
        "evidence": outcome.evidence,
        "hypotheses": outcome.hypotheses,
        "log_analysis": outcome.log_analysis,
        "runbook_analysis": outcome.runbook_analysis,
        "kubernetes_analysis": outcome.kubernetes_analysis,
        "runbook_name": outcome.runbook_name,
        "runbook_solution": outcome.runbook_solution,
        "investigation_status": IncidentStatus.INVESTIGATING,
        "retry_count": retry_count,
    }
