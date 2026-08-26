"""Investigation Agent: orchestrates the parallel investigation sub-agents.

Fans out to Log Analysis, Kubernetes, and Runbook in parallel (mirroring the
"Investigation Agent" stage in updated-flow-v2.md), then consolidates their
findings into the aggregated evidence/hypotheses lists that
investigation_summary and rca_report already consume. Pure agent-layer code --
no LangGraph/state coupling; ``app.services.investigation_service`` does the
state translation.

Each sub-agent is isolated in its own try/except so one failing (bad LLM
response, network error, missing knowledge base) never sinks the other two --
the orchestrator always returns a full ``InvestigationOutcome`` with a
per-source Evidence entry describing what happened.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

from app.agents.investigation.kubernetes.agent import KubernetesAgent
from app.agents.investigation.log_analysis.agent import LogAnalysisAgent
from app.agents.investigation.runbook.agent import run_runbook_agent
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis
from app.domain.models.incident import Incident
from app.graph.state import RunbookResult, RunbookStatus
from app.llm.client import get_chat_model
from app.tools.mock.kubernetes import MockKubernetesTool
from app.tools.mock.logs import MockLogTool


@dataclass
class InvestigationOutcome:
    evidence: list[Evidence] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    log_analysis: Evidence | None = None
    runbook_analysis: Evidence | None = None
    kubernetes_analysis: Evidence | None = None


def _fallback_evidence(source: str, finding: str, severity: str = "unknown") -> Evidence:
    return Evidence(evidence_id=f"ev-{source}-{uuid.uuid4().hex[:8]}", source=source, finding=finding, severity=severity)


async def _run_log_analysis(
    incident: Incident, model: str | None
) -> tuple[Evidence, list[Evidence], list[Hypothesis]]:
    try:
        agent = LogAnalysisAgent(get_chat_model(model=model), MockLogTool())
        result = await agent.run(incident)
    except Exception as exc:  # noqa: BLE001 -- isolate this sub-agent's failure from the other two
        failure = _fallback_evidence("log_analysis", f"Log analysis investigation failed: {exc}")
        return failure, [failure], []
    if result.evidence:
        return result.evidence[0], result.evidence, result.hypotheses
    fallback = _fallback_evidence("log_analysis", result.summary or "No log evidence returned.", "info")
    return fallback, [fallback], result.hypotheses


async def _run_kubernetes(
    incident: Incident, model: str | None
) -> tuple[Evidence, list[Evidence], list[Hypothesis]]:
    try:
        agent = KubernetesAgent(get_chat_model(model=model), MockKubernetesTool())
        result = await agent.run(incident)
    except Exception as exc:  # noqa: BLE001 -- isolate this sub-agent's failure from the other two
        failure = _fallback_evidence("kubernetes", f"Kubernetes investigation failed: {exc}")
        return failure, [failure], []
    if result.evidence:
        return result.evidence[0], result.evidence, result.hypotheses
    fallback = _fallback_evidence("kubernetes", result.summary or "No Kubernetes evidence returned.", "info")
    return fallback, [fallback], result.hypotheses


def _run_runbook(
    incident: Incident, classification: ClassificationResult | None
) -> tuple[Evidence, list[Hypothesis]]:
    try:
        result: RunbookResult = run_runbook_agent(incident.model_dump(), classification)
    except Exception as exc:  # noqa: BLE001 -- backstop; run_runbook_agent already catches its own errors
        return _fallback_evidence("runbook", f"Runbook lookup failed: {exc}"), []

    if result.status == RunbookStatus.MATCHED and result.hypothesis is not None:
        score = result.score if result.score is not None else 0.0
        evidence = _fallback_evidence(
            "runbook", f"Matched runbook '{result.matched_title}' (relevance score {score:.2f}).", "medium"
        )
        return evidence, [result.hypothesis]
    if result.status == RunbookStatus.NO_MATCH:
        return _fallback_evidence("runbook", "No matching runbook found for this incident.", "info"), []
    return _fallback_evidence("runbook", f"Runbook lookup error: {result.error}", "unknown"), []


async def run_investigation(
    incident: Incident,
    classification: ClassificationResult | None = None,
    log_analysis_model: str | None = None,
    kubernetes_model: str | None = None,
) -> InvestigationOutcome:
    """Fan out to Log Analysis, Kubernetes, and Runbook in parallel, then consolidate."""
    (log_representative, log_evidence, log_hypotheses), (
        kubernetes_representative,
        kubernetes_evidence,
        kubernetes_hypotheses,
    ), (runbook_representative, runbook_hypotheses) = await asyncio.gather(
        _run_log_analysis(incident, log_analysis_model),
        _run_kubernetes(incident, kubernetes_model),
        asyncio.to_thread(_run_runbook, incident, classification),
    )

    return InvestigationOutcome(
        evidence=[*log_evidence, runbook_representative, *kubernetes_evidence],
        hypotheses=[*log_hypotheses, *runbook_hypotheses, *kubernetes_hypotheses],
        log_analysis=log_representative,
        runbook_analysis=runbook_representative,
        kubernetes_analysis=kubernetes_representative,
    )
