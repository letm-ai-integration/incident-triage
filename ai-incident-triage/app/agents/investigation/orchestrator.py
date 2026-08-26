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

from app.agents.investigation.kubernetes.agent import KubernetesAgent
from app.agents.investigation.log_analysis.agent import LogAnalysisAgent
from app.agents.investigation.runbook.agent import (
    MIN_RELEVANCE_SCORE,
    run_runbook_agent,
)
from app.domain.enums.incident_type import IncidentType
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.incident import Incident
from app.tools.mock.kubernetes import MockKubernetesTool
from app.tools.mock.logs import MockLogTool

logger = logging.getLogger(__name__)

_SIGNALS = (
    "error", "fail", "timeout", "exception", "connection", "refused",
    "crash", "oom", "unavailable", "exhausted", "back-off",
)


@dataclass
class InvestigationOutcome:
    evidence: list[Evidence] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    log_analysis: Evidence | None = None
    kubernetes_analysis: Evidence | None = None
    runbook_analysis: Evidence | None = None
    confidence: float = 0.35


def _tool_incident_type(incident: Incident, classification: ClassificationResult | None) -> str:
    """Map the incident to the mock tools' type vocabulary."""
    if classification is not None:
        mapping = {
            IncidentType.DATABASE: "DATABASE",
            IncidentType.KUBERNETES: "KUBERNETES",
        }
        if classification.incident_type in mapping:
            return mapping[classification.incident_type]
        return "APPLICATION"
    return str(incident.tags[0]) if incident.tags else "APPLICATION"


def _keyword_signals(texts: list[str]) -> list[str]:
    lowered = [t.lower() for t in texts if t]
    return [kw for kw in _SIGNALS if any(kw in t for t in lowered)]


async def _log_evidence(
    incident: Incident, llm, classification: ClassificationResult | None = None
) -> Evidence:
    """Log analysis via the LLM agent when available, else keyword fallback.

    The deterministic fallback scans the incident's own telemetry -- raw logs
    plus description and alert names, since mock incidents often carry their
    strongest signals outside ``raw_logs``.
    """
    try:
        if llm is not None:
            result = await LogAnalysisAgent(llm, MockLogTool()).run(
                incident, classification
            )
            finding = result.summary or "Log analysis completed."
            signals = _keyword_signals([finding])
        else:
            texts = list(incident.raw_logs) + [incident.description]
            texts += [
                str(a.get("alert_name") or a.get("name") or "") if isinstance(a, dict) else str(a)
                for a in incident.raw_alerts
            ]
            matched = _keyword_signals(texts)
            finding = (
                f"Found error signals in incident telemetry: {', '.join(matched[:5])}."
                if matched else "No error signals detected in logs."
            )
            signals = matched
        return Evidence(
            evidence_id="ev-log-1",
            source="log_analysis",
            finding=finding,
            severity="high" if signals else "info",
            raw_data={"matched_signals": signals[:10], "log_count": len(incident.raw_logs)},
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
    """Kubernetes analysis via the LLM agent when available, else fallback."""
    try:
        incident_type = _tool_incident_type(incident, classification)
        tool_output = await MockKubernetesTool().run(
            incident_type=incident_type, service=incident.service,
            namespace=incident.metadata.get("namespace", "default"),
        )
        if llm is not None:
            result = await KubernetesAgent(llm, MockKubernetesTool()).run(
                incident, classification
            )
            degraded = bool(result.hypotheses)
        else:
            # Deterministic mode analyzes only the incident's OWN telemetry;
            # the mock tool's canned template events would otherwise fabricate
            # degradation for incidents that have none.
            events_text = " ".join(str(e) for e in incident.raw_events)
            alerts = " ".join(
                str(a.get("alert_name") or a.get("name") or "") if isinstance(a, dict) else str(a)
                for a in incident.raw_alerts
            )
            degraded = bool(_keyword_signals([events_text, alerts]))
        finding = (
            "Workload health check flagged degradation in pod status/events."
            if degraded else "Workload health check passed."
        )
        return Evidence(
            evidence_id="ev-k8s-1",
            source="kubernetes",
            finding=finding,
            severity="medium" if degraded else "info",
            raw_data={
                "pod_statuses": list(tool_output.pod_statuses),
                "recent_events": list(tool_output.recent_events),
                "degraded": degraded,
            },
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
    """Runbook retrieval via the RAG-based runbook agent (no chat LLM needed)."""
    result = run_runbook_agent(alert_data, classification)
    if result.status.value == "MATCHED" and result.hypothesis is not None:
        evidence = Evidence(
            evidence_id="ev-rb-1",
            source="runbook",
            finding=f"Matched runbook '{result.matched_title}' "
                    f"(score {result.score:.2f}).",
            severity="info" if result.score < MIN_RELEVANCE_SCORE else "medium",
            raw_data={
                "matched_runbooks": [result.matched_title],
                "score": result.score,
            },
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

    logger.info(
        "[investigation.orchestrator] starting investigation incident=%s llm_backed=%s",
        incident.incident_id,
        llm is not None,
    )
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
    )
    logger.info(
        "[investigation.orchestrator] completed incident=%s confidence=%.2f "
        "evidence_count=%d hypotheses=%d log_severity=%s k8s_severity=%s runbook=%r",
        incident.incident_id,
        outcome.confidence,
        len(outcome.evidence),
        len(outcome.hypotheses),
        outcome.log_analysis.severity if outcome.log_analysis else "n/a",
        outcome.kubernetes_analysis.severity if outcome.kubernetes_analysis else "n/a",
        outcome.runbook_analysis.finding[:80] if outcome.runbook_analysis else "n/a",
    )
    return outcome


def investigate(
    incident: Incident,
    classification: ClassificationResult | None = None,
    llm=None,
) -> InvestigationOutcome:
    """Synchronous entry point for graph nodes/services (asyncio.run bridge)."""
    import asyncio

    return asyncio.run(run_investigation(incident, classification, llm=llm))
