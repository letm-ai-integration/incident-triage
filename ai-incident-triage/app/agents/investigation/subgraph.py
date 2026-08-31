"""Investigation phase subgraph: how the orchestrator runs its sub-agents.

The Investigation Orchestrator (app/agents/investigation/orchestrator.py) is
the single owner of the investigation phase. Internally it executes this
compiled LangGraph subgraph:

    START ──┬─> log_analysis ───┐
            ├─> kubernetes ─────┼──> synthesize_outcome ──> END
            └─> runbook ────────┘

The three sub-agent nodes run in parallel (LangGraph fan-out); each wraps one
existing sub-agent implementation from the orchestrator module. The
``synthesize_outcome`` node aggregates all per-subagent outputs into the
structured result (``evidence`` / ``hypotheses`` / ``confidence``) that the
orchestrator maps back onto the shared ``IncidentState`` via
``app/services/investigation_service.py`` -- so nothing produced here is
isolated inside the orchestrator and every downstream node can consume it.

This module is also what ``scripts/generate_investigation_png.py`` renders:
the committed PNG is generated programmatically from this exact definition,
never hand-drawn.
"""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START

from app.agents.investigation.orchestrator import (
    _kubernetes_evidence,
    _log_evidence,
    _runbook_evidence,
    _synthesize_outcome,
)
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis
from app.domain.models.incident import Incident
from app.graph.builder import add_edge, add_node, create_graph
from app.graph.tracing import trace_async, trace_sync


class InvestigationPhaseState(TypedDict, total=False):
    """State of the investigation phase subgraph.

    Inputs (incident/classification/llm) mirror the orchestrator's arguments;
    the per-subagent keys feed the aggregator; ``evidence``/``hypotheses``/
    ``confidence`` are the aggregated outputs written into shared graph state.
    """

    # Inputs
    incident: Incident
    classification: ClassificationResult | None
    llm: Any

    # Per-subagent outputs
    log_analysis: Evidence
    kubernetes_analysis: Evidence
    runbook_analysis: Evidence
    runbook_hypothesis: Hypothesis | None

    # Runbook-backed resolution surfaced by the runbook sub-agent
    runbook_name: str | None
    runbook_solution: str | None

    # Aggregated output -> shared IncidentState
    evidence: list[Evidence]
    hypotheses: list[Hypothesis]
    confidence: float


async def log_analysis_node(state: InvestigationPhaseState) -> dict:
    """Subagent 1: LLM-backed log analysis (deterministic keyword fallback)."""
    incident = state["incident"]
    result = await trace_async(
        "log_analysis",
        {"incident_id": incident.incident_id, "log_lines": len(incident.raw_logs)},
        _log_evidence(incident, state.get("llm"), state.get("classification")),
    )
    return {"log_analysis": result}


async def kubernetes_node(state: InvestigationPhaseState) -> dict:
    """Subagent 2: LLM-backed Kubernetes analysis (deterministic fallback)."""
    incident = state["incident"]
    result = await trace_async(
        "kubernetes",
        {"incident_id": incident.incident_id, "events": len(incident.raw_events)},
        _kubernetes_evidence(incident, state.get("classification"), state.get("llm")),
    )
    return {"kubernetes_analysis": result}


def runbook_node(state: InvestigationPhaseState) -> dict:
    """Subagent 3: RAG-based runbook retrieval (no chat LLM needed)."""
    incident = state["incident"]
    alert_data = {
        "title": incident.title,
        "description": incident.description,
        "raw_logs": incident.raw_logs,
    }
    evidence, hypothesis = trace_sync(
        "runbook",
        {"incident_id": incident.incident_id, "title": incident.title},
        _runbook_evidence,
        alert_data,
        state.get("classification"),
    )
    return {
        "runbook_analysis": evidence,
        "runbook_hypothesis": hypothesis,
        "runbook_name": evidence.raw_data.get("runbook_name"),
        "runbook_solution": evidence.raw_data.get("solution"),
    }


def synthesize_outcome_node(state: InvestigationPhaseState) -> dict:
    """Aggregate the parallel subagent outputs into the structured outcome."""
    evidence, hypotheses, confidence = _synthesize_outcome(
        state["log_analysis"],
        state["kubernetes_analysis"],
        state["runbook_analysis"],
        state.get("runbook_hypothesis"),
    )
    return {"evidence": evidence, "hypotheses": hypotheses, "confidence": confidence}


def build_investigation_phase_graph():
    """Assemble (and compile) the investigation phase subgraph."""
    builder = create_graph(state_schema=InvestigationPhaseState)

    add_node(builder, "log_analysis", log_analysis_node)
    add_node(builder, "kubernetes", kubernetes_node)
    add_node(builder, "runbook", runbook_node)
    add_node(builder, "synthesize_outcome", synthesize_outcome_node)

    # Fan-out: all three subagents start together (parallel execution).
    for subagent in ("log_analysis", "kubernetes", "runbook"):
        add_edge(builder, START, subagent)
        add_edge(builder, subagent, "synthesize_outcome")

    add_edge(builder, "synthesize_outcome", END)
    return builder.compile()


investigation_phase_graph = build_investigation_phase_graph()
