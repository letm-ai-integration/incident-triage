"""Phase 1 (Polish) -- fixed-structure HTML/CSS incident report email.

Locks in the single reusable template (``app/prompts/templates/incident_report_email.html``)
rendered via ``app.services.email_report_renderer.render_html_email_report``:
all 8 body sections + header/footer appear in order with inline-CSS table layout,
every required edge-case fallback resolves, and all incident text is HTML-escaped.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.enums.incident_type import IncidentType
from app.domain.enums.priority import Priority
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import Evidence, EvidenceCollection
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.report import IncidentReport, RunbookReference
from app.domain.models.root_cause import RootCauseAnalysis
from app.domain.models.verification import VerificationResult
from app.services.email_report_renderer import render_html_email_report


def _report(**overrides) -> IncidentReport:
    """A full INC-006-shaped report (runbook available, clear environment/priority)."""
    base: dict = {
        "incident_id": "INC-006",
        "classification": ClassificationResult(
            incident_type=IncidentType.DATABASE,
            priority=Priority.P1,
            confidence=0.9,
            reasoning="connection pool exhaustion under sustained checkout load",
            affected_services=["checkout-service", "checkout-db"],
            agrees_with_rule=True,
        ),
        "evidence": EvidenceCollection(
            summary="2 evidence items",
            items=[
                Evidence(
                    evidence_id="ev-log-1",
                    source="log_analysis",
                    finding="connection pool exhausted, waiting threads blocking",
                    severity="high",
                    provenance="OBSERVED",
                ),
                Evidence(
                    evidence_id="ev-k8s-1",
                    source="kubernetes",
                    finding="no applicable runbook",
                    severity="info",
                ),
            ],
        ),
        "root_cause": RootCauseAnalysis(
            primary_cause=Hypothesis(
                hypothesis_id="H1",
                description="connection pool exhaustion",
                confidence=0.9,
                supporting_evidence=["ev-log-1"],
                label=HypothesisLabel.LIKELY,
            ),
            contributing_factors=[
                Hypothesis(
                    hypothesis_id="H2",
                    description="traffic spike 4x above baseline",
                    confidence=0.6,
                    label=HypothesisLabel.POSSIBLE,
                )
            ],
            confidence_score=0.9,
            affected_components=["checkout-db"],
        ),
        "recommended_actions": [
            "Raise the HikariCP max-pool-size and shorten connection timeout",
            "Validate pool sizing against the flash-sale traffic spike",
        ],
        "runbook_references": [
            RunbookReference(
                runbook_id="db",
                title="database--checkout-service",
                url="runbooks/database--checkout-service",
            )
        ],
        "verification": VerificationResult(
            is_resolved=False,
            needs_reinvestigation=False,
        ),
        "created_at": datetime(2026, 8, 6, 10, 20, tzinfo=UTC),
        "incident_title": "Database Connection Failure on checkout-db",
        "incident_description": (
            "checkout-service cannot acquire a connection from the primary database "
            "(checkout-db) and customers see 'unable to complete order'."
        ),
        "environment": "PRODUCTION",
    }
    base.update(overrides)
    return IncidentReport(**base)


_SECTIONS_IN_ORDER = [
    "1 · Incident Overview",
    "2 · Environment",
    "3 · Impacted Services",
    "4 · Impact Assessment",
    "5 · Investigation Findings",
    "6 · Root Cause Analysis",
    "7 · Recommended Remediation",
    "8 · Investigation Status",
]


def test_full_template_renders_all_sections_in_order_with_header_and_footer():
    html = render_html_email_report(_report(), run_id="run-abc123")

    # Header band: incident id, severity badge, generated timestamp.
    assert "Incident INC-006" in html
    assert "P1" in html  # severity badge
    assert "2026-08-06 10:20 UTC" in html  # generated timestamp

    # The 8 body sections appear in the fixed order.
    positions = [html.index(h) for h in _SECTIONS_IN_ORDER]
    assert positions == sorted(positions), list(zip(_SECTIONS_IN_ORDER, positions))

    # Footer band: run id + automated-report reminder.
    assert "Run ID: run-abc123" in html
    assert "automated investigation report" in html

    # Content is bound from the validated report fields (not invented).
    assert "checkout-service" in html
    assert "checkout-db" in html
    assert "Production" in html  # environment, title-cased from PRODUCTION
    assert "connection pool exhaustion" in html  # root cause
    assert "Runbook Status:" in html
    assert "Applicable runbook found" in html
    assert "traffic spike 4x above baseline" in html  # contributing factor
    assert "Raise the HikariCP max-pool-size" in html  # recommended action
    assert "Completed" in html  # Investigation status row
    assert "Pending On-Call Action" in html  # Remediation status row


def test_missing_environment_falls_back_to_not_specified():
    html = render_html_email_report(_report(environment=None), run_id="r1")
    assert "Environment: Not specified" in html


def test_missing_priority_renders_not_specified_badge():
    classification = _report().classification.model_copy(update={"priority": None})
    html = render_html_email_report(_report(classification=classification), run_id="r2")
    assert "Not specified" in html


def test_empty_impacted_services_renders_fallback_row():
    classification = _report().classification.model_copy(update={"affected_services": []})
    html = render_html_email_report(_report(classification=classification))
    assert "No impacted services could be identified from available evidence." in html


def test_empty_findings_renders_fallback_item():
    report = _report(
        evidence=EvidenceCollection(summary="none"),
        root_cause=RootCauseAnalysis(
            primary_cause=_report().root_cause.primary_cause,
            confidence_score=0.9,
        ),
    )
    html = render_html_email_report(report)
    assert "No findings could be established from available evidence." in html


def test_missing_runbook_renders_unavailable_callout():
    html = render_html_email_report(_report(runbook_references=[]))
    assert "No applicable runbook found" in html
    assert "Runbook remediation unavailable" in html
    assert "On-call engineering action is required" in html


def test_runbook_title_used_when_no_recommended_actions():
    html = render_html_email_report(_report(recommended_actions=[]))
    assert "Follow runbook: database--checkout-service" in html


def test_inconclusive_root_cause_renders_gray_badge():
    inconclusive = RootCauseAnalysis(
        primary_cause=Hypothesis(
            hypothesis_id="H3",
            description="no conclusive signal",
            confidence=0.2,
            label=HypothesisLabel.UNLIKELY,
        ),
        confidence_score=0.2,
    )
    html = render_html_email_report(_report(root_cause=inconclusive))
    assert "Root cause could not be conclusively determined" in html


def test_run_id_falls_back_to_not_recorded():
    html = render_html_email_report(_report(), run_id=None)
    assert "Run ID: Not recorded" in html


def test_no_none_null_or_empty_artifacts():
    html = render_html_email_report(_report(), run_id=None)
    for banned in (">None<", "null", "undefined", "<td></td>", "{{", "}}"):
        assert banned not in html, banned


def test_incident_text_is_html_escaped():
    html = render_html_email_report(
        _report(
            incident_description="<script>alert('x')</script> & \"quoted\"",
            incident_title="& <b>bold</b>",
        )
    )
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html
    assert "<b>bold</b>" not in html
