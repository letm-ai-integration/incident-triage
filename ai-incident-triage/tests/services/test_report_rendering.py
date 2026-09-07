"""Phase 5: canonical report/notification rendering.

Locks in the exact Phase 5 Markdown structure and the population rules: the
renderer only echoes validated state, reports the three allowed Root-Cause
states, never claims remediation was applied without verification, shows the
mandatory no-runbook blockquote, and surfaces claim-validation downgrades.
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.domain.enums.incident_type import IncidentType
from app.domain.enums.priority import Priority
from app.domain.models.claim_validation import ClaimCategory, ClaimValidationFinding
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import Evidence, EvidenceCollection
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.report import IncidentReport, RunbookReference
from app.domain.models.root_cause import RootCauseAnalysis
from app.domain.models.verification import VerificationResult
from app.services.rca_report_service import (
    remediation_status,
    render_markdown_report,
    root_cause_determination,
    root_cause_state_short,
)


def _classification() -> ClassificationResult:
    return ClassificationResult(
        incident_type=IncidentType.DATABASE,
        priority=Priority.P1,
        confidence=0.9,
        reasoning="pool exhaustion under load",
        affected_services=["checkout-service"],
        agrees_with_rule=True,
    )


def _evidence() -> EvidenceCollection:
    return EvidenceCollection(
        items=[
            Evidence(
                evidence_id="ev-log-1",
                source="log_analysis",
                finding="connection pool exhausted, waiting threads blocking",
                severity="high",
            ),
            Evidence(
                evidence_id="ev-k8s-1",
                source="kubernetes",
                finding="no applicable runbook",
                severity="info",
            ),
        ],
        summary="2 evidence items",
    )


def _hypothesis(
    description: str = "connection pool exhaustion",
    confidence: float = 0.9,
    label: HypothesisLabel = HypothesisLabel.LIKELY,
) -> Hypothesis:
    return Hypothesis(
        hypothesis_id="H1",
        description=description,
        confidence=confidence,
        supporting_evidence=["ev-log-1"],
        contradicting_evidence=[],
        label=label,
    )


def _report(**overrides) -> IncidentReport:
    root_cause = RootCauseAnalysis(
        primary_cause=_hypothesis(),
        contributing_factors=[],
        confidence_score=0.9,
        claim_validation=[
            ClaimValidationFinding(
                hypothesis_id="H1",
                category=ClaimCategory.EMPTY_SOURCE,
                claim="no k8s telemetry",
                supported=False,
                penalty=0.15,
                qualifier="telemetry unavailable",
                detail="evidence is a report, not observed data",
            )
        ],
    )
    base: dict = {
        "incident_id": "INC-R",
        "classification": _classification(),
        "evidence": _evidence(),
        "hypotheses": [_hypothesis()],
        "root_cause": root_cause,
        "recommended_actions": ["Investigate and remediate: connection pool exhaustion"],
        "verification": VerificationResult(is_resolved=False, needs_reinvestigation=True),
        "created_at": datetime(2026, 8, 1, tzinfo=UTC),
        "incident_title": "checkout pool exhausted",
        "incident_description": "reported 500s on checkout",
        "environment": "production",
    }
    base.update(overrides)
    return IncidentReport(**base)


def test_render_has_canonical_phase5_structure():
    markdown = render_markdown_report(_report())
    for heading in (
        "## Incident Summary",
        "### Incident Overview",
        "### Environment",
        "### Impacted Services",
        "### Impact Assessment",
        "### Investigation Findings",
        "### Root Cause Analysis",
        "### Recommended Remediation",
        "### Investigation Status",
    ):
        assert heading in markdown
    assert "This investigation is limited to analysis and recommendation" in markdown


def test_render_overview_distinguishes_reported_vs_observed():
    markdown = render_markdown_report(_report())
    assert "checkout-service" in markdown
    assert "reported 500s on checkout" in markdown
    assert "connection pool exhausted, waiting threads blocking" in markdown
    assert "production" in markdown


def test_render_root_cause_states_map_from_validated_confidence():
    assert root_cause_determination(_report().root_cause) == "Confirmed root cause"
    assert root_cause_state_short(_report().root_cause) == "Confirmed"

    probable = RootCauseAnalysis(
        primary_cause=_hypothesis(confidence=0.55, label=HypothesisLabel.POSSIBLE),
        contributing_factors=[], confidence_score=0.55,
    )
    assert root_cause_determination(probable) == "Probable root cause"
    assert root_cause_state_short(probable) == "Probable"

    inconclusive = RootCauseAnalysis(
        primary_cause=_hypothesis(confidence=0.2, label=HypothesisLabel.UNLIKELY),
        contributing_factors=[], confidence_score=0.2,
    )
    assert root_cause_determination(inconclusive) == "Root cause could not be conclusively determined"
    assert root_cause_state_short(inconclusive) == "Inconclusive"


def test_render_surfaces_claim_validation_downgrades():
    markdown = render_markdown_report(_report())
    assert "Claim not independently verified" in markdown
    assert "telemetry unavailable" in markdown


def test_render_no_runbook_shows_mandatory_blockquote():
    markdown = render_markdown_report(_report())
    assert "**Runbook Status:** No applicable runbook found" in markdown
    assert "**Runbook remediation unavailable:**" in markdown
    assert "On-call engineering action is required" in markdown


def test_render_with_runbook_shows_steps():
    report = _report(
        runbook_references=[
            RunbookReference(runbook_id="db", title="database--checkout-service", url="runbooks/database--checkout-service")
        ]
    )
    markdown = render_markdown_report(report)
    assert "**Runbook Status:** Applicable runbook found" in markdown
    assert "**When an Applicable Runbook Is Available:**" in markdown
    assert "database--checkout-service" in markdown


def test_render_remediation_never_claims_applied_when_unresolved():
    markdown = render_markdown_report(_report())
    remediation_section = markdown.split("### Recommended Remediation", 1)[1]
    remediation_section = remediation_section.split("### Investigation Status", 1)[0]
    for banned in ("fixed", "remediated", "restarted", "scaled", "increased"):
        assert banned.lower() not in remediation_section.lower()
    # "resolved" must not appear as an applied-claim in the remediation section
    assert "not yet executed" in remediation_section


def test_remediation_status_mapping():
    report = _report()
    assert remediation_status(report) == "Pending On-Call Action"
    report_none = _report(recommended_actions=[], runbook_references=[])
    assert remediation_status(report_none) == "Not Applied"
    report_applied = _report(
        verification=VerificationResult(
            is_resolved=True,
            resolution_evidence="recovery verified from telemetry",
            needs_reinvestigation=False,
        )
    )
    assert remediation_status(report_applied) == "Applied"


def test_render_investigation_status():
    markdown = render_markdown_report(_report())
    assert "- **Investigation:** Completed" in markdown
    assert "- **Root-Cause Analysis:** Confirmed" in markdown
    assert "- **Remediation:** Pending On-Call Action" in markdown