"""RCA & Report Agent: synthesizes a root cause analysis from investigation evidence.

Confidence is never LLM-only: app/rules/confidence.py computes a deterministic
ceiling from the hypotheses' own labels/scores first, and the LLM's stated
confidence_score may never exceed it (see _reconcile_with_ceiling below).

This agent produces the typed RootCauseAnalysis only. Assembling the full
IncidentReport (evidence + hypotheses + root cause + recommended actions) and
rendering it as a human-readable Markdown report is app/services/rca_report_service.py's
job, not this agent's -- keeps this agent's contract narrow per the HLD's
per-agent typed I/O principle.
"""
from __future__ import annotations

import logging

from app.agents.rca_report.parser import parse_rca_response
from app.agents.rca_report.prompt import SYSTEM_PROMPT, build_user_prompt
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import EvidenceCollection
from app.domain.models.hypothesis import Hypothesis
from app.domain.models.incident import Incident
from app.domain.models.root_cause import RootCauseAnalysis
from app.llm.client import create_structured_agent
from app.rules.confidence import compute_confidence_ceiling

logger = logging.getLogger(__name__)


def generate_root_cause_analysis(
    incident: Incident,
    classification: ClassificationResult,
    evidence: EvidenceCollection,
    hypotheses: list[Hypothesis],
    model: str | None = None,
) -> RootCauseAnalysis:
    """Synthesize a RootCauseAnalysis for ``incident`` from collected evidence/hypotheses.

    ``hypotheses`` are the candidate hypotheses already proposed by the
    investigation sub-agents (e.g. the runbook agent's match) -- this agent's
    job is to weigh them against each other and the evidence, not originate
    them from nothing.
    """
    ceiling = compute_confidence_ceiling(hypotheses)
    logger.info(
        "[rca_report.agent] generating RCA incident=%s evidence_count=%d hypotheses=%d ceiling=%.2f",
        incident.incident_id,
        len(evidence.evidence) if hasattr(evidence, "evidence") else -1,
        len(hypotheses),
        ceiling,
    )
    agent = create_structured_agent(
        system_prompt=SYSTEM_PROMPT,
        output_schema=RootCauseAnalysis,
        model=model,
    )
    try:
        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": build_user_prompt(incident, classification, evidence, hypotheses, ceiling),
                    }
                ]
            }
        )
    except Exception:
        logger.exception(
            "[rca_report.agent] LLM invocation failed -- check provider base_url "
            "reachability, API key, and network/proxy settings"
        )
        raise
    rca = parse_rca_response(response)
    reconciled = _reconcile_with_ceiling(rca, ceiling)
    if reconciled.confidence_score != rca.confidence_score:
        logger.info(
            "[rca_report.agent] confidence %.2f capped to deterministic ceiling %.2f",
            rca.confidence_score,
            reconciled.confidence_score,
        )
    logger.info(
        "[rca_report.agent] RCA generated confidence=%.2f",
        reconciled.confidence_score,
    )
    return reconciled


def _reconcile_with_ceiling(rca: RootCauseAnalysis, ceiling: float) -> RootCauseAnalysis:
    return rca.model_copy(update={"confidence_score": min(rca.confidence_score, ceiling)})
