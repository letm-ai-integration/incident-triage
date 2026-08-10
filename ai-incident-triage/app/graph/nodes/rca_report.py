# v2: determines root cause + confidence AND generates the final incident
# report. Merges the former v1 rca and report nodes.
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from langchain_core.runnables import RunnableConfig

from app.domain.constants import DEFAULT_CONFIDENCE_SCORE
from app.domain.enums.incident_type import IncidentType
from app.domain.enums.priority import Priority
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import EvidenceCollection
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.report import IncidentReport
from app.domain.models.root_cause import RootCauseAnalysis, TimelineEvent
from app.domain.models.verification import VerificationResult
from app.graph.builder import get_deps
from app.graph.state import IncidentState


def rca_report_node(state: IncidentState, config: Optional[RunnableConfig] = None) -> dict:
    """Write the ``RootCauseAnalysis`` and the draft ``IncidentReport``."""
    deps = get_deps(config)
    service = deps.get("rca_report_service", _default_rca_report)
    try:
        update = service(state, deps)
    except Exception as exc:
        update = {"errors": state.get("errors", []) + [f"rca_report failed: {exc}"]}
    update.setdefault("current_step", "rca_report")
    return update


def _default_rca_report(state: IncidentState, deps: dict) -> dict:
    """Fallback RCA: pick the top hypothesis as the primary cause and draft the report."""
    incident = state.get("incident")
    incident_id = state.get("incident_id") or (incident.incident_id if incident else "UNKNOWN")
    classification = _reconstruct_classification(state)
    evidence = state.get("evidence", [])
    hypotheses = state.get("hypotheses", [])
    top = max(hypotheses, key=lambda h: h.confidence) if hypotheses else _fallback_hypothesis()
    summary = state.get("investigation_summary") or {}

    root_cause = RootCauseAnalysis(
        primary_cause=top,
        contributing_factors=[h for h in hypotheses if h.hypothesis_id != top.hypothesis_id],
        confidence_score=top.confidence,
        timeline=[TimelineEvent(timestamp="T+0", description="Incident reported.")],
        affected_components=(
            list(classification.affected_services) if classification.affected_services else []
        ),
    )

    expected_outcome = {
        "expectation": f"Incident resolved by addressing '{top.description}'.",
        "action": f"Apply the recommended fix for '{top.description}' and confirm recovery.",
    }

    report = IncidentReport(
        incident_id=incident_id,
        classification=classification,
        evidence=EvidenceCollection(
            items=evidence,
            summary=summary.get("summary", f"{len(evidence)} evidence item(s) collected"),
        ),
        hypotheses=hypotheses,
        root_cause=root_cause,
        recommended_actions=[expected_outcome["action"]],
        runbook_references=[],
        verification=VerificationResult(is_resolved=False, needs_reinvestigation=True),
        created_at=datetime.now(timezone.utc),
    )

    return {
        "root_cause": root_cause,
        "rca_confidence": root_cause.confidence_score,
        "incident_report": report,
        "expected_outcome": expected_outcome,
    }


def _reconstruct_classification(state: IncidentState) -> ClassificationResult:
    existing = state.get("classification")
    if existing is not None:
        return existing
    return ClassificationResult(
        incident_type=state.get("incident_type") or IncidentType.UNKNOWN,
        priority=state.get("severity") or Priority.P2,
        confidence=state.get("classification_confidence") or DEFAULT_CONFIDENCE_SCORE,
        reasoning="Reconstructed from flattened state fields.",
        affected_services=[],
        suggested_teams=[],
        rule_based_priority=state.get("severity"),
        agrees_with_rule=True,
    )


def _fallback_hypothesis() -> Hypothesis:
    return Hypothesis(
        hypothesis_id="hyp-fallback",
        description="No hypotheses produced; cause could not be determined during investigation.",
        confidence=DEFAULT_CONFIDENCE_SCORE,
        supporting_evidence=[],
        contradicting_evidence=[],
        label=HypothesisLabel.POSSIBLE,
    )
