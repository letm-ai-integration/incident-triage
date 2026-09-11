"""Tests for the Notification Agent.

The LLM, on-call lookup, and email send are all mocked -- these tests never
make network calls or read external state.
"""
from datetime import UTC, datetime

import pytest

from app.agents.notification import agent as agent_module
from app.agents.notification.agent import NotificationResult, run_notification_agent
from app.agents.notification.parser import (
    NotificationSubject,
    parse_notification_response,
)
from app.domain.enums.incident_type import IncidentType
from app.domain.enums.priority import Priority
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import EvidenceCollection
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.report import IncidentReport
from app.domain.models.root_cause import RootCauseAnalysis
from app.domain.models.verification import VerificationResult
from app.tools.adapters.resend_email import EmailSendError
from app.tools.mock.oncall import OnCallContact


def _oncall() -> OnCallContact:
    return OnCallContact(
        name="Ayush Sharma",
        role="Backend On-Call Engineer",
        email="ayush.sharma@example.com",
        team="backend",
        status="on-call",
    )


def _report() -> IncidentReport:
    return IncidentReport(
        incident_id="INC-42",
        classification=ClassificationResult(
            incident_type=IncidentType.APPLICATION,
            priority=Priority.P1,
            confidence=0.95,
            reasoning="mock reasoning",
            affected_services=["payments-api"],
            agrees_with_rule=True,
        ),
        evidence=EvidenceCollection(summary="mock evidence"),
        root_cause=RootCauseAnalysis(
            primary_cause=Hypothesis(
                hypothesis_id="H1",
                description="connection pool exhaustion in payments-api",
                confidence=0.9,
                supporting_evidence=["E1"],
                label=HypothesisLabel.LIKELY,
            ),
            confidence_score=0.9,
        ),
        recommended_actions=["increase max connections to 200"],
        verification=VerificationResult(
            is_resolved=True,
            resolution_evidence="thread dump showed pooled connections exhausted",
            needs_reinvestigation=False,
        ),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        environment="staging",
    )


class _FakeAgent:
    def __init__(self, structured_response):
        self._structured_response = structured_response
        self.invoked_with = None

    def invoke(self, payload):
        self.invoked_with = payload
        return {"structured_response": self._structured_response}


def _fake_send(captured):
    def send(to, subject, html_body):
        captured["to"] = to
        captured["subject"] = subject
        captured["html_body"] = html_body
        return "msg-123"

    return send


def test_success_path_sends_email_to_oncall_contact(monkeypatch):
    captured = {}
    monkeypatch.setattr(agent_module, "get_current_oncall", lambda: _oncall())
    monkeypatch.setattr(
        agent_module,
        "create_structured_agent",
        lambda **kwargs: _FakeAgent(
            NotificationSubject(subject="[P1] INC-42 payments-api RCA report")
        ),
    )
    monkeypatch.setattr(agent_module, "send_email", _fake_send(captured))

    result = run_notification_agent(_report())

    assert isinstance(result, NotificationResult)
    assert result.success is True
    assert result.error is None
    assert result.recipient == "ayush.sharma@example.com"
    assert result.message_id == "msg-123"
    assert captured["to"] == "ayush.sharma@example.com"
    assert captured["subject"] == "[P1] INC-42 payments-api RCA report"
    # The body is ALWAYS the fixed HTML template -- never LLM output.
    assert "<table" in captured["html_body"]
    assert "1 · Incident Overview" in captured["html_body"]
    assert "8 · Investigation Status" in captured["html_body"]


def test_llm_subject_failure_still_sends_styled_template(monkeypatch):
    captured = {}
    monkeypatch.setattr(agent_module, "get_current_oncall", lambda: _oncall())

    def boom(**kwargs):
        raise RuntimeError("LLM unreachable")

    monkeypatch.setattr(agent_module, "create_structured_agent", boom)
    monkeypatch.setattr(agent_module, "send_email", _fake_send(captured))

    pending = _report().model_copy(
        update={"verification": VerificationResult(is_resolved=False, needs_reinvestigation=True)}
    )
    result = run_notification_agent(pending)

    assert result.success is True
    # Deterministic honest subject + styled template body.
    assert "(remediation pending)" in captured["subject"]
    assert "<table" in captured["html_body"]


def test_llm_subject_claiming_resolution_is_rejected_when_pending(monkeypatch):
    captured = {}
    monkeypatch.setattr(agent_module, "get_current_oncall", lambda: _oncall())
    monkeypatch.setattr(
        agent_module,
        "create_structured_agent",
        lambda **kwargs: _FakeAgent(NotificationSubject(subject="[P1] INC-42 incident FIXED")),
    )
    monkeypatch.setattr(agent_module, "send_email", _fake_send(captured))

    pending = _report().model_copy(
        update={"verification": VerificationResult(is_resolved=False, needs_reinvestigation=True)}
    )
    result = run_notification_agent(pending)

    assert result.success is True
    # Honesty gate replaces the claiming subject with the deterministic one.
    assert "FIXED" not in captured["subject"]
    assert "(remediation pending)" in captured["subject"]


def test_send_refuses_non_html_body(monkeypatch):
    """The adapter must fail loudly rather than degrade to plain text."""
    import types

    import app.tools.adapters.resend_email as adapter

    monkeypatch.setattr(
        adapter, "get_settings",
        lambda: types.SimpleNamespace(
            resend_api_key="test-key", resend_from_name="T", resend_from_email="t@example.com"
        ),
    )
    with pytest.raises(EmailSendError, match="no HTML markup"):
        adapter.send_email("a@example.com", "s", "plain text, no markup at all")


def test_multi_incident_bodies_are_always_styled_html(monkeypatch):
    """Full + edge-case reports: every body is the styled HTML template."""
    captured: list[dict] = []

    def capturing_send(to, subject, html_body):
        captured.append({"to": to, "subject": subject, "html_body": html_body})
        return "msg-x"

    monkeypatch.setattr(agent_module, "get_current_oncall", lambda: _oncall())
    monkeypatch.setattr(
        agent_module, "create_structured_agent",
        lambda **kwargs: _FakeAgent(NotificationSubject(subject="s")),
    )
    monkeypatch.setattr(agent_module, "send_email", capturing_send)

    variants = [
        _report(),  # full: runbook + environment + resolution evidence
        _report().model_copy(update={"runbook_references": []}),  # no runbook
        _report().model_copy(update={"environment": None}),  # missing env
        _report().model_copy(
            update={
                "verification": VerificationResult(is_resolved=False, needs_reinvestigation=True)
            }
        ),  # pending
    ]
    for report in variants:
        result = run_notification_agent(report)
        assert result.success is True

    assert len(captured) == len(variants)
    for msg in captured:
        body = msg["html_body"]
        for marker in ("<table", "border-radius", "1 · Incident Overview", "8 · Investigation Status"):
            assert marker in body, (marker, msg["subject"])


def test_llm_prompt_is_composed_from_report_fields(monkeypatch):
    monkeypatch.setattr(agent_module, "get_current_oncall", lambda: _oncall())
    fake_agent = _FakeAgent(NotificationSubject(subject="s"))
    monkeypatch.setattr(agent_module, "create_structured_agent", lambda **kwargs: fake_agent)
    monkeypatch.setattr(agent_module, "send_email", _fake_send({}))

    run_notification_agent(_report())

    prompt = fake_agent.invoked_with["messages"][0]["content"]
    assert "INC-42" in prompt
    assert "payments-api" in prompt
    assert "P1" in prompt
    assert "connection pool exhaustion in payments-api" in prompt
    assert "increase max connections to 200" in prompt
    assert "ayush.sharma@example.com" in prompt
    # The prompt must carry every field the nine canonical sections need.
    assert "environment: staging" in prompt
    assert "affected_services: payments-api" in prompt
    assert "priority: P1" in prompt
    assert "root_cause_determination: Confirmed root cause" in prompt
    assert "contributing_factors:" in prompt
    assert "investigation_findings:" in prompt
    assert "impact_independently_observed:" in prompt
    assert "runbook_status: No applicable runbook found" in prompt


def test_send_failure_returns_error_result(monkeypatch):
    monkeypatch.setattr(agent_module, "get_current_oncall", lambda: _oncall())
    monkeypatch.setattr(
        agent_module,
        "create_structured_agent",
        lambda **kwargs: _FakeAgent(NotificationSubject(subject="s")),
    )

    def boom(to, subject, html_body):
        raise EmailSendError("RESEND_API_KEY is not configured")

    monkeypatch.setattr(agent_module, "send_email", boom)

    result = run_notification_agent(_report())

    assert isinstance(result, NotificationResult)
    assert result.success is False
    assert result.error == "RESEND_API_KEY is not configured"
    assert result.recipient is None
    assert result.message_id is None


def test_missing_oncall_data_returns_error_result(monkeypatch):
    def raise_missing():
        raise FileNotFoundError("On-call mock data file not found")

    monkeypatch.setattr(agent_module, "get_current_oncall", raise_missing)

    result = run_notification_agent(_report())

    assert result.success is False
    assert "not found" in (result.error or "")


def test_content_safety_guardrail_blocks_send(monkeypatch):
    monkeypatch.setattr(agent_module, "get_current_oncall", lambda: _oncall())
    monkeypatch.setattr(
        agent_module,
        "create_structured_agent",
        lambda **kwargs: _FakeAgent(NotificationSubject(subject="s")),
    )
    send_calls = []
    monkeypatch.setattr(agent_module, "send_email", lambda **kwargs: send_calls.append(kwargs))

    from app.guardrails.models import GuardrailResult

    monkeypatch.setattr(
        agent_module,
        "check_content_safety",
        lambda node_name, content: GuardrailResult(
            node_name=node_name, passed=False, findings=["safety: matched keyword 'x'"]
        ),
    )

    result = run_notification_agent(_report())

    assert result.success is False
    assert "content-safety guardrail" in result.error
    assert send_calls == []


def test_parser_raises_on_missing_structured_response():
    with pytest.raises(TypeError, match="structured_response"):
        parse_notification_response({"messages": []})


def test_parser_raises_on_wrong_type():
    with pytest.raises(TypeError, match="structured_response"):
        parse_notification_response({"structured_response": {"not": "a model"}})


def test_template_fallback_uses_canonical_structure_and_honest_remediation():
    from app.agents.notification.agent import _draft_email_template

    report = _report().model_copy(
        update={
            "verification": VerificationResult(
                is_resolved=False, needs_reinvestigation=True
            )
        }
    )
    email = _draft_email_template(report)

    assert "(remediation pending)" in email.subject
    # Full canonical template: header band + all 8 body sections, in order.
    sections = [
        "1 · Incident Overview",
        "2 · Environment",
        "3 · Impacted Services",
        "4 · Impact Assessment",
        "5 · Investigation Findings",
        "6 · Root Cause Analysis",
        "7 · Recommended Remediation",
        "8 · Investigation Status",
    ]
    positions = [email.body.index(h) for h in sections]
    assert positions == sorted(positions), [(h, p) for h, p in zip(sections, positions)]
    # Environment and priority must be visible and correctly populated, not
    # inferred or invented.
    assert "Environment: Staging" in email.body  # from the incident's own value
    assert ">P1</span>" in email.body  # the incident's actual priority badge
    assert "Runbook Status:" in email.body
    assert "Remediation:" in email.body
    assert "Contributing Factors" in email.body
    assert "not yet executed" in email.body
    for banned in ("fixed", "resolved", "remediated", "restarted", "scaled", "increased"):
        assert banned not in email.body.lower()


def test_template_fallback_resolved_subject_has_no_pending_suffix():
    from app.agents.notification.agent import _draft_email_template

    resolved = _report()
    resolved = resolved.model_copy(
        update={
            "verification": VerificationResult(
                is_resolved=True,
                resolution_evidence="recovery verified from telemetry",
                needs_reinvestigation=False,
            )
        }
    )
    email = _draft_email_template(resolved)
    assert "(remediation pending)" not in email.subject
    assert "Remediation:" in email.body


def test_notification_system_prompt_is_subject_only_with_honesty_gates():
    from app.agents.notification.prompt import SYSTEM_PROMPT

    # The LLM only drafts the subject -- the body is the pipeline's fixed HTML
    # template, so the prompt must NOT ask it to compose a body anymore.
    assert "SUBJECT LINE" in SYSTEM_PROMPT
    assert "body is NOT yours to write" in SYSTEM_PROMPT
    assert "verification_is_resolved" in SYSTEM_PROMPT
    assert "remediation_status" in SYSTEM_PROMPT
    assert '"resolved", "fixed", "remediated"' in SYSTEM_PROMPT
    assert "(remediation pending)" in SYSTEM_PROMPT
    assert "Plain text only" in SYSTEM_PROMPT