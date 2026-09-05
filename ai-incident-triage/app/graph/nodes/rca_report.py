# v2: determines root cause + confidence AND generates the final incident
# report. Merges the former v1 rca and report nodes.
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

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

logger = logging.getLogger(__name__)


def rca_report_node(state: IncidentState, config: RunnableConfig | None = None) -> dict:
    """Write the ``RootCauseAnalysis`` and the draft ``IncidentReport``."""
    deps = get_deps(config)
    service = deps.get("rca_report_service", _default_rca_report)
    try:
        update = service(state, deps)
    except Exception as exc:  # noqa: BLE001 -- node boundary: record and continue
        update = {"errors": state.get("errors", []) + [f"rca_report failed: {exc}"]}
    update.setdefault("current_step", "rca_report")
    return update


def _resolve_runbook_doc(incident) -> Any:
    """Best-effort name-keyed runbook lookup for the RCA step.

    Uses ``resolve_by_name`` (token-matches the incident title/description
    against each ``runbooks/*.md`` display name and returns a doc with its
    ``## Solution``). Failures degrade to ``None`` -- a broken runbook lookup
    must never fail the RCA step.
    """
    if incident is None:
        return None
    try:
        from app.agents.investigation.runbook.resolver import resolve_by_name

        return resolve_by_name(incident.title, incident.description)
    except Exception:
        logger.exception("[rca_report] name-keyed runbook resolution failed")
        return None


def _default_rca_report(state: IncidentState, deps: dict) -> dict:
    """Fallback RCA: pick the top hypothesis as the primary cause and draft the report."""
    incident = state.get("incident")
    incident_id = state.get("incident_id") or (incident.incident_id if incident else "UNKNOWN")
    classification = _reconstruct_classification(state)
    evidence = state.get("evidence", [])
    hypotheses = state.get("hypotheses", [])
    top = max(hypotheses, key=lambda h: h.confidence) if hypotheses else _fallback_hypothesis()
    summary = state.get("investigation_summary") or {}

    # Name-keyed runbook match: surfaces the runbook's actual ``## Solution``
    # in the final result/notification, phrased as a recommendation for the
    # on-call engineer -- this system only diagnoses, it does not remediate.
    runbook_doc = _resolve_runbook_doc(incident)
    runbook_references: list[RunbookReference] = []
    if runbook_doc is not None:
        runbook_references = [
            RunbookReference(
                runbook_id=runbook_doc.name,
                title=runbook_doc.name,
                url=runbook_doc.file,
            )
        ]

    root_cause = RootCauseAnalysis(
        primary_cause=top,
        contributing_factors=[h for h in hypotheses if h.hypothesis_id != top.hypothesis_id],
        confidence_score=top.confidence,
        timeline=[TimelineEvent(timestamp="T+0", description="Incident reported.")],
        affected_components=(
            list(classification.affected_services) if classification.affected_services else []
        ),
    )

    if runbook_doc is not None:
        expected_outcome = {
            "expectation": (
                f"A matching runbook was found for \"{runbook_doc.name}\"; if the "
                "on-call engineer applies its recommended fix, the service should recover."
            ),
            "action": (
                f'A matching runbook was found for "{runbook_doc.name}". '
                f"Recommended (on-call): {runbook_doc.solution}"
            ),
        }
    else:
        expected_outcome = {
            "expectation": (
                f"If the runbook-recommended fix for '{top.description}' is applied "
                "by the on-call engineer, the service should recover."
            ),
            "action": (
                f"Recommended (on-call): apply the runbook fix for '{top.description}' "
                "and confirm recovery."
            ),
        }

    recommended_actions = [expected_outcome["action"]]
    for ref in runbook_references:
        recommended_actions.append(f"Follow runbook: {ref.title} ({ref.url})")

    report = IncidentReport(
        incident_id=incident_id,
        classification=classification,
        evidence=EvidenceCollection(
            items=evidence,
            summary=summary.get("summary", f"{len(evidence)} evidence item(s) collected"),
        ),
        hypotheses=hypotheses,
        root_cause=root_cause,
        recommended_actions=recommended_actions,
        runbook_references=runbook_references,
        verification=VerificationResult(is_resolved=False, needs_reinvestigation=True),
        created_at=datetime.now(UTC),
    )

    update: dict = {
        "root_cause": root_cause,
        "rca_confidence": root_cause.confidence_score,
        "incident_report": report,
        "expected_outcome": expected_outcome,
    }
    if runbook_doc is not None:
        update["runbook_name"] = runbook_doc.name
        update["runbook_solution"] = runbook_doc.solution
    return update


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
