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
from app.graph.builder import create_graph
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

    # Aggregated output -> shared IncidentState
    evidence: list[Evidence]
    hypotheses: list[Hypothesis]
    confidence: float


async def log_analysis_node(state: InvestigationPhaseState) -> dict:
    """Subagent 1: LLM-backed log analysis (deterministic keyword fallback).

    Traced: records a ``subagent`` entry on the running node's ``agent_trace``
    (and live status on the event bus) so the UI can show this fan-out call
    with its own status/duration.
    """
    incident = state["incident"]
    return {
        "log_analysis": await trace_async(
            "log_analysis",
            {"incident": incident.incident_id, "service": incident.service},
            _log_evidence(incident, state.get("llm"), state.get("classification")),
        )
    }


async def kubernetes_node(state: InvestigationPhaseState) -> dict:
    """Subagent 2: LLM-backed Kubernetes analysis (deterministic fallback)."""
    incident = state["incident"]
    return {
        "kubernetes_analysis": await trace_async(
            "kubernetes",
            {"incident": incident.incident_id, "service": incident.service},
            _kubernetes_evidence(incident, state.get("classification"), state.get("llm")),
        )
    }


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
        {"incident": incident.incident_id, "service": incident.service},
        _runbook_evidence,
        alert_data,
        state.get("classification"),
    )
    return {"runbook_analysis": evidence, "runbook_hypothesis": hypothesis}


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

    builder.add_node("log_analysis", log_analysis_node)
    builder.add_node("kubernetes", kubernetes_node)
    builder.add_node("runbook", runbook_node)
    builder.add_node("synthesize_outcome", synthesize_outcome_node)

    # Fan-out: all three subagents start together (parallel execution).
    for subagent in ("log_analysis", "kubernetes", "runbook"):
        builder.add_edge(START, subagent)
        builder.add_edge(subagent, "synthesize_outcome")

    builder.add_edge("synthesize_outcome", END)
    return builder.compile()


investigation_phase_graph = build_investigation_phase_graph()
