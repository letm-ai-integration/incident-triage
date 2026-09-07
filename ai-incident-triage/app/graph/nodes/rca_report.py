# v2: determines root cause + confidence AND generates the final incident
# report. Merges the former v1 rca and report nodes.
from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig

from app.domain.constants import DEFAULT_CONFIDENCE_SCORE
from app.domain.enums.incident_type import IncidentType
from app.domain.enums.priority import Priority
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import EvidenceCollection
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.report import IncidentReport, RunbookReference
from app.domain.models.root_cause import RootCauseAnalysis, TimelineEvent
from app.domain.models.verification import VerificationResult
from app.graph.builder import get_deps
from app.graph.state import IncidentState
from app.services.evidence_service import validate_hypotheses
from app.services.hypothesis_service import finalize_root_cause


def rca_report_node(state: IncidentState, config: RunnableConfig | None = None) -> dict:
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
    """Fallback RCA: pick the top hypothesis as the primary cause and draft the report.

    Runs the Phase 3 deterministic claim validation before finalization: any
    hypothesis claim not backed by collected telemetry is downgraded (confidence
    penalty + wording qualifier) and the RCA confidence is capped by the shared
    deterministic ceiling, so the report never presents an unsupported claim as
    a confirmed root cause.
    """
    incident = state.get("incident")
    incident_id = state.get("incident_id") or (incident.incident_id if incident else "UNKNOWN")
    classification = _reconstruct_classification(state)
    evidence = state.get("evidence", [])
    hypotheses = state.get("hypotheses", [])
    findings = validate_hypotheses(incident, evidence, hypotheses)
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
    if hypotheses:
        # Claims to validate only exist when the investigation produced
        # hypotheses. The no-hypotheses fallback path keeps its pre-Phase-3
        # semantics: with nothing to ground, nothing is downgraded.
        root_cause = finalize_root_cause(root_cause, findings, hypotheses)
    else:
        root_cause = root_cause.model_copy(update={"claim_validation": findings})

    expected_outcome = {
        "expectation": f"Incident resolved by addressing '{top.description}'.",
        "action": f"Apply the recommended fix for '{top.description}' and confirm recovery.",
    }

    runbook_name = state.get("runbook_name")
    runbook_solution = state.get("runbook_solution")
    runbook_references: list = []
    if runbook_name and runbook_solution:
        runbook_references = [RunbookReference(
            runbook_id=runbook_name,
            title=runbook_name,
            url=f"runbooks/{runbook_name}",
        )]
        # Explicitly cite the runbook-backed resolution in the final result.
        expected_outcome = {
            "expectation": f"Incident resolved by addressing '{runbook_name}'.",
            "action": f"A matching runbook was found for \"{runbook_name}\". "
                      f"The recommended resolution from the runbook is: {runbook_solution}",
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
        recommended_actions=_recommended_actions(expected_outcome, runbook_references),
        runbook_references=runbook_references,
        verification=VerificationResult(is_resolved=False, needs_reinvestigation=True),
        created_at=datetime.now(UTC),
        incident_title=incident.title if incident else None,
        incident_description=incident.description if incident else None,
        environment=incident.environment.value if incident else None,
    )

    return {
        "root_cause": root_cause,
        "rca_confidence": root_cause.confidence_score,
        "incident_report": report,
        "expected_outcome": expected_outcome,
        "claim_validation": findings,
    }


def _recommended_actions(expected_outcome: dict, runbook_references: list) -> list:
    """Build recommended actions, including the runbook-backed resolution."""
    actions = [expected_outcome.get("action", "")]
    for ref in runbook_references:
        actions.append(f"Follow runbook: {ref.title} ({ref.url})")
    return [a for a in actions if a]


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
