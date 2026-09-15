"""Dedicated guardrail-quarantine notification template + renderer.

Locks in ``app/services/quarantine_email_renderer.py`` /
``app/prompts/templates/guardrail_quarantine_email.html``:

* the header label is FIXED across every quarantined incident and the band is
  visually distinct from the Incident Summary coral banner;
* one table row per guardrail finding detail (never merged);
* every field degrades gracefully (no blank sections, no raw None/null);
* every piece of incident-derived text is HTML-escaped -- quarantined content is
  by definition untrusted/flagged input.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.enums.environment import Environment
from app.domain.models.incident import Incident
from app.services.quarantine_email_renderer import (
    QUARANTINE_ALERT_LABEL,
    render_quarantine_html_email,
)


def _incident(**overrides) -> Incident:
    base: dict = {
        "incident_id": "INC-TEST-1",
        "title": "Test incident",
        "description": "Test description",
        "source": "unit-test",
        "service": "checkout-service",
        "environment": Environment.PRODUCTION,
        "timestamp": datetime(2026, 9, 10, tzinfo=UTC),
    }
    base.update(overrides)
    return Incident(**base)


def _finding(check: str, *details: str, node: str = "ingestion") -> dict:
    return {"node": node, "check": check, "passed": False, "findings": list(details)}


def test_header_label_is_fixed_and_band_is_distinct_from_incident_summary():
    html = render_quarantine_html_email(_incident(), [])
    # Fixed alert wording, branding the alert type (not the incident).
    assert QUARANTINE_ALERT_LABEL == "QUARANTINED — NOT SUBMITTED FOR AUTOMATED TRIAGE"
    assert QUARANTINE_ALERT_LABEL in html
    # Warning band, deliberately not the Incident Summary template's coral.
    assert "background-color:#8a1c1c" in html
    assert "#ff4b4b" not in html
    # Table-based, inline-CSS only (Outlook-safe), never the summary template.
    assert "<table" in html and "border-radius" in html
    assert "1 · Incident Overview" not in html
    assert "3 · Impacted Services" not in html


def test_label_is_constant_across_different_incidents():
    first = render_quarantine_html_email(_incident(incident_id="INC-A"), [])
    second = render_quarantine_html_email(
        _incident(incident_id="INC-B", service="community-uploads"), []
    )
    assert QUARANTINE_ALERT_LABEL in first and QUARANTINE_ALERT_LABEL in second
    assert "INC-A" in first and "INC-B" in second
    assert "community-uploads" in second


def test_one_row_per_finding_detail_across_multiple_checks():
    findings = [
        _finding("check_prompt_injection", "prompt_injection: matched phrase 'jailbreak'"),
        _finding("check_pii", "pii:email detected", "pii:credit_card_number detected"),
    ]
    html = render_quarantine_html_email(_incident(), findings)
    # All three detail strings rendered as separate rows -- nothing merged/dropped.
    assert "prompt_injection: matched phrase &#39;jailbreak&#39;" in html
    assert "pii:email detected" in html
    assert "pii:credit_card_number detected" in html
    assert html.count("check_prompt_injection") == 1
    assert html.count("check_pii") == 2
    assert "prompt_injection" in html and ">pii<" in html


def test_each_guardrail_category_renders_its_own_row_data():
    pii = render_quarantine_html_email(
        _incident(), [_finding("check_pii", "pii:email detected")]
    )
    injection = render_quarantine_html_email(
        _incident(),
        [_finding("check_prompt_injection", "prompt_injection: matched phrase 'x'")],
    )
    safety = render_quarantine_html_email(
        _incident(),
        [_finding("check_content_safety", "safety: matched keyword 'how to make explosives'")],
    )
    assert "check_pii" in pii and ">pii<" in pii and "check_prompt_injection" not in pii
    assert "check_prompt_injection" in injection and ">prompt_injection<" in injection
    assert "check_content_safety" in safety and ">safety<" in safety
    assert "how to make explosives" in safety


def test_empty_findings_falls_back_to_single_raw_message_row():
    html = render_quarantine_html_email(
        _incident(), [], raw_quarantine_message="raw guardrail message"
    )
    assert "raw guardrail message" in html
    assert ">guardrail<" in html and ">quarantine<" in html
    # Exactly one data row exists beyond the header row + callout box.
    assert html.count("<tr>") >= 1
    assert "(no findings recorded)" not in html


def test_finding_with_empty_detail_list_falls_back_not_blank():
    html = render_quarantine_html_email(
        _incident(), [{"node": "ingestion", "check": "check_pii", "passed": False, "findings": []}]
    )
    assert "check_pii" in html
    assert "was flagged by an input guardrail" in html
    assert ">None<" not in html and ">null<" not in html


def test_missing_service_and_environment_render_not_specified():
    unknown_service = render_quarantine_html_email(_incident(service=""), [])
    assert "Not specified · PRODUCTION" in unknown_service

    placeholder = render_quarantine_html_email(_incident(service="unknown"), [])
    assert "Not specified · PRODUCTION" in placeholder

    both_missing = render_quarantine_html_email(
        _incident().model_copy(update={"service": "", "environment": None}), []
    )
    assert "Not specified · Not specified" in both_missing


def test_incident_derived_text_is_html_escaped():
    """Quarantined content is by definition untrusted -- never insert it raw."""
    html = render_quarantine_html_email(
        _incident(title="<script>alert('x')</script> & \"quoted\""),
        [_finding("check_pii", "pii:email <img src=x onerror=alert(1)> detected")],
    )
    assert "<script>alert" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;img src=x" in html
    assert "&amp;" in html


def test_pii_in_finding_detail_is_redacted():
    html = render_quarantine_html_email(
        _incident(),
        [_finding("check_pii", "pii:email leaked to ops@corp.com from jane.doe@example.com")],
    )
    assert "ops@corp.com" not in html
    assert "jane.doe@example.com" not in html
    assert "[REDACTED:EMAIL]" in html


def test_run_id_renders_and_falls_back_when_absent():
    with_run = render_quarantine_html_email(_incident(), [], run_id="cli-inc-123")
    assert "Run ID: cli-inc-123" in with_run

    without = render_quarantine_html_email(_incident(), [], run_id=None)
    assert "Run ID: Not recorded" in without


def test_required_action_defaults_to_exact_wording_when_category_unknown():
    html = render_quarantine_html_email(_incident(), [])
    assert (
        "Please review the raw incident content manually before deciding whether "
        "to re-submit it for automated triage." in html
    )


def test_required_action_is_data_driven_per_category():
    injection = render_quarantine_html_email(
        _incident(),
        [_finding("check_prompt_injection", "prompt_injection: matched phrase 'x'")],
    )
    assert "Do not feed the submitted content to any automated or LLM-based tooling." in injection
    assert "re-submit it for automated triage." not in injection

    safety = render_quarantine_html_email(
        _incident(), [_finding("check_content_safety", "safety: matched keyword 'x'")]
    )
    assert "trust-and-safety/security review process" in safety


def test_no_none_null_or_template_artifacts():
    html = render_quarantine_html_email(
        _incident(title="", service=""), [_finding("check_pii", "pii:email detected")], run_id=None
    )
    for banned in (">None<", "null", "undefined", "<td></td>", "{{", "}}", "{%"):
        assert banned not in html, banned


def test_notify_quarantine_sends_the_dedicated_template(monkeypatch):
    """Phase 3 wiring: the quarantine path uses the new template, not the Report one."""
    from app.agents.notification import agent as agent_module
    from app.agents.notification.agent import notify_quarantine
    from app.tools.mock.oncall import OnCallContact

    captured: dict = {}

    def fake_send(to, subject, html_body):
        captured.update(to=to, subject=subject, html_body=html_body)
        return "msg-quarantine"

    monkeypatch.setattr(
        agent_module,
        "get_current_oncall",
        lambda: OnCallContact(
            name="A", role="On-Call", email="oncall@example.com", team="backend", status="on-call"
        ),
    )
    monkeypatch.setattr(agent_module, "send_email", fake_send)

    result = notify_quarantine(
        _incident(),
        [_finding("check_content_safety", "safety: matched keyword 'how to make explosives'")],
        run_id="cli-inc-TEST",
    )

    assert result.success is True
    assert result.message_id == "msg-quarantine"
    body = captured["html_body"]
    assert QUARANTINE_ALERT_LABEL in body
    assert "how to make explosives" in body
    assert "Run ID: cli-inc-TEST" in body
    # It must never be the investigation-complete Incident Summary template.
    assert "1 · Incident Overview" not in body
    assert "#ff4b4b" not in body

