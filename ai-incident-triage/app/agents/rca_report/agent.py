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

from app.agents.rca_report.parser import parse_rca_response
from app.agents.rca_report.prompt import SYSTEM_PROMPT, build_user_prompt
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import EvidenceCollection
from app.domain.models.hypothesis import Hypothesis
from app.domain.models.incident import Incident
from app.domain.models.root_cause import RootCauseAnalysis
from app.llm.client import create_structured_agent
from app.rules.confidence import compute_confidence_ceiling


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
    agent = create_structured_agent(
        system_prompt=SYSTEM_PROMPT,
        output_schema=RootCauseAnalysis,
        model=model,
    )
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
    rca = parse_rca_response(response)
    return _reconcile_with_ceiling(rca, ceiling)


def _reconcile_with_ceiling(rca: RootCauseAnalysis, ceiling: float) -> RootCauseAnalysis:
    return rca.model_copy(update={"confidence_score": min(rca.confidence_score, ceiling)})
