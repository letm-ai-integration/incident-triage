"""Investigation orchestrator: coordinates the parallel investigation sub-agents.

This is the single place that knows about all three sub-agents:

- ``LogAnalysisAgent``   (app/agents/investigation/log_analysis) -- LLM-backed,
  falls back to deterministic keyword analysis of the incident's own logs when
  no LLM is available.
- ``KubernetesAgent``    (app/agents/investigation/kubernetes)     -- LLM-backed,
  same fallback strategy over the incident's raw events/alerts.
- runbook agent          (app/agents/investigation/runbook)       -- RAG-based
  FAISS retrieval; needs no chat LLM at all.

The orchestrator never raises for agent failures: a failing sub-agent becomes
an ``Evidence`` item with ``severity="info"`` describing the failure, so one
broken dependency degrades the investigation instead of killing the graph run.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.agents.investigation.kubernetes.agent import analyze_kubernetes_with_fallback
from app.agents.investigation.log_analysis.agent import analyze_logs_with_fallback
from app.agents.investigation.runbook.agent import (
    MIN_RELEVANCE_SCORE,
    run_runbook_agent,
)
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.incident import Incident
from app.logging_utils import agent_entry, agent_output, agent_exit, agent_error
from app.graph.tracing import suppress_node_events, unsuppress_node_events

logger = logging.getLogger(__name__)

_SIGNALS = (
    "error", "fail", "timeout", "exception", "connection", "refused",
    "crash", "oom", "unavailable", "exhausted", "back off",
)


@dataclass
class InvestigationOutcome:
    evidence: list[Evidence] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    log_analysis: Evidence | None = None
    kubernetes_analysis: Evidence | None = None
    runbook_analysis: Evidence | None = None
    confidence: float = 0.35
    runbook_name: str | None = None
    runbook_solution: str | None = None


def _keyword_signals(texts: list[str]) -> list[str]:
    lowered = [t.lower() for t in texts if t]
    return [kw for kw in _SIGNALS if any(kw in t for t in lowered)]


async def _log_evidence(
    incident: Incident, llm, classification: ClassificationResult | None = None
) -> Evidence:
    """Log analysis via the LogAnalysisAgent (always executes).

    Delegates to analyze_logs_with_fallback which uses the LLM agent when
    available, or falls back to deterministic keyword analysis internally.
    """
    try:
        result = await analyze_logs_with_fallback(incident, classification, llm)
        finding = result.summary or "Log analysis completed."
        matched = _keyword_signals(
            list(incident.raw_logs) + [incident.description] + [
                str(a.get("alert_name") or a.get("name") or "") if isinstance(a, dict) else str(a)
                for a in incident.raw_alerts
            ]
        )
        return Evidence(
            evidence_id="ev-log-1",
            source="log_analysis",
            finding=finding,
            severity="high" if matched else "info",
            raw_data={"matched_signals": matched[:10], "log_count": len(incident.raw_logs)},
        )
    except Exception as exc:  # noqa: BLE001 -- degrade, never kill the run
        return Evidence(
            evidence_id="ev-log-1",
            source="log_analysis",
            finding=f"Log analysis failed: {exc}",
            severity="info",
            raw_data={"error": str(exc)},
        )


async def _kubernetes_evidence(
    incident: Incident, classification: ClassificationResult | None, llm
) -> Evidence:
    """Kubernetes analysis via the KubernetesAgent (always executes).

    Delegates to analyze_kubernetes_with_fallback, which retrieves model-data
    ``k8s`` evidence through the RAG store and (optionally) the LLM, else uses
    the deterministic grounded fallback. The agent's own evidence raw_data
    already carries the retrieved pod/namespace/event provenance.
    """
    try:
        result = await analyze_kubernetes_with_fallback(incident, classification, llm)
        degraded = bool(result.hypotheses)
        finding = result.summary or (
            "Workload health check flagged degradation in pod status/events."
            if degraded else "Workload health check passed."
        )
        raw = dict(result.evidence[0].raw_data) if result.evidence else {}
        raw.update({"degraded": degraded})
        return Evidence(
            evidence_id="ev-k8s-1",
            source="kubernetes",
            finding=finding,
            severity="medium" if degraded else "info",
            raw_data=raw,
        )
    except Exception as exc:  # noqa: BLE001
        return Evidence(
            evidence_id="ev-k8s-1",
            source="kubernetes",
            finding=f"Kubernetes analysis failed: {exc}",
            severity="info",
            raw_data={"error": str(exc)},
        )


def _runbook_evidence(
    alert_data: dict, classification: ClassificationResult | None
) -> tuple[Evidence, Hypothesis | None]:
    """Runbook retrieval via the RAG-based runbook agent (no chat LLM needed).

    Also surfaces the runbook's name + extracted **Solution** (when a named
    runbook matched) in the evidence ``raw_data`` / ``finding`` so downstream
    report steps can explicitly cite the runbook-backed resolution.
    """
    result = run_runbook_agent(alert_data, classification)
    if result.status.value == "MATCHED" and result.hypothesis is not None:
        raw: dict = {
            "matched_runbooks": [result.matched_title],
            "score": result.score,
        }
        if result.runbook_name:
            raw["runbook_name"] = result.runbook_name
        if result.solution:
            raw["solution"] = result.solution
            finding = f"Matched runbook '{result.runbook_name or result.matched_title}' with a documented resolution."
        else:
            finding = f"Matched runbook '{result.matched_title}' (score {result.score:.2f})."
        evidence = Evidence(
            evidence_id="ev-rb-1",
            source="runbook",
            finding=finding,
            severity="info" if result.score < MIN_RELEVANCE_SCORE else "medium",
            raw_data=raw,
        )
        return evidence, result.hypothesis
    reason = result.error or "No matching runbook found for this incident pattern."
    return (
        Evidence(
            evidence_id="ev-rb-1",
            source="runbook",
            finding=reason,
            severity="info",
            raw_data={"matched_runbooks": []},
        ),
        None,
    )


def _synthesize_outcome(
    log_evidence: Evidence,
    kubernetes_evidence: Evidence,
    runbook_evidence: Evidence,
    runbook_hypothesis: Hypothesis | None,
) -> tuple[list[Evidence], list[Hypothesis], float]:
    """Aggregate per-subagent outputs into evidence, hypotheses, confidence.

    Confidence reflects how much *independent* evidence converged:
    base 0.35, +0.25 for error signals in logs, +0.2 for degraded k8s
    state, +0.15 for a matched runbook -- capped at 0.95. A runbook match
    alone is never enough: without at least one corroborating error signal
    from telemetry the outcome stays below the resolution threshold (0.5)
    so verification correctly sends it through the reinvestigation loop.
    """
    evidence = [log_evidence, runbook_evidence, kubernetes_evidence]

    confidence = 0.35
    if log_evidence.severity == "high":
        confidence += 0.25
    if kubernetes_evidence.severity != "info":
        confidence += 0.2
    if runbook_hypothesis is not None:
        confidence += 0.15
    if log_evidence.severity == "info" and kubernetes_evidence.severity == "info":
        confidence = min(confidence, 0.45)
    confidence = min(confidence, 0.95)

    primary = Hypothesis(
        hypothesis_id="hyp-1",
        description=(
            f"Primary cause relates to: {runbook_hypothesis.description[:200]}"
            if runbook_hypothesis is not None and confidence >= 0.5
            else f"Incident signals: {log_evidence.finding} "
                 f"{kubernetes_evidence.finding}"
        ),
        confidence=confidence,
        supporting_evidence=[e.evidence_id for e in evidence if e.severity != "info"],
        contradicting_evidence=[],
        label=HypothesisLabel.LIKELY if confidence >= 0.7 else HypothesisLabel.POSSIBLE,
    )
    hypotheses = [primary]
    if runbook_hypothesis is not None:
        if log_evidence.severity == "info" and kubernetes_evidence.severity == "info":
            # A retrieval hit alone must not masquerade as a high-confidence
            # root cause: with zero corroborating telemetry it stays below the
            # resolution threshold so verification routes to reinvestigation.
            runbook_hypothesis = runbook_hypothesis.model_copy(
                update={
                    "confidence": min(runbook_hypothesis.confidence, 0.45),
                    "label": HypothesisLabel.POSSIBLE,
                }
            )
        hypotheses.append(runbook_hypothesis)
    return evidence, hypotheses, confidence


async def run_investigation(
    incident: Incident,
    classification: ClassificationResult | None = None,
    llm=None,
) -> InvestigationOutcome:
    """Coordinate the investigation phase and return the aggregated outcome.

    The three sub-agents are executed through the compiled investigation
    phase subgraph (app/agents/investigation/subgraph.py): log analysis,
    Kubernetes, and runbook retrieval start in parallel; a synthesize node
    then aggregates their outputs. This function stays the single owner of
    the phase -- it prepares inputs, runs the subgraph, and maps the result
    onto ``InvestigationOutcome`` which the graph service writes into shared
    state (see app/services/investigation_service.py).
    """
    # Local import: the subgraph imports this module's sub-agent wrappers.
    from app.agents.investigation.subgraph import investigation_phase_graph

    agent_entry("InvestigationOrchestrator", f"incident={incident.incident_id} llm_backed={llm is not None}")
    # The subgraph's own nodes share the (contextvar) run context; suppress their
    # node-level events so they don't show up as bogus top-level nodes -- their
    # sub-agent calls are surfaced via trace helpers instead.
    suppress_node_events()
    try:
        result = await investigation_phase_graph.ainvoke(
            {"incident": incident, "classification": classification, "llm": llm}
        )
        outcome = InvestigationOutcome(
            evidence=result["evidence"],
            hypotheses=result["hypotheses"],
            log_analysis=result["log_analysis"],
            kubernetes_analysis=result["kubernetes_analysis"],
            runbook_analysis=result["runbook_analysis"],
            confidence=result["confidence"],
            runbook_name=result.get("runbook_name"),
            runbook_solution=result.get("runbook_solution"),
        )
        agent_output(
            "InvestigationOrchestrator",
            f"confidence={outcome.confidence:.2f} evidence={len(outcome.evidence)} "
            f"hypotheses={len(outcome.hypotheses)} log={outcome.log_analysis.severity if outcome.log_analysis else 'n/a'} "
            f"k8s={outcome.kubernetes_analysis.severity if outcome.kubernetes_analysis else 'n/a'}",
        )
    except Exception as exc:
        agent_error("InvestigationOrchestrator", exc)
        raise
    finally:
        unsuppress_node_events()
        agent_exit("InvestigationOrchestrator")
    return outcome


def investigate(
    incident: Incident,
    classification: ClassificationResult | None = None,
    llm=None,
) -> InvestigationOutcome:
    """Synchronous entry point for graph nodes/services (asyncio.run bridge)."""
    import asyncio

    return asyncio.run(run_investigation(incident, classification, llm=llm))
