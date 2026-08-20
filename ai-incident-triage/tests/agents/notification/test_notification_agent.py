"""Tests for the Notification Agent.

The LLM, on-call lookup, and email send are all mocked -- these tests never
make network calls or read external state.
"""
from datetime import UTC, datetime

import pytest

from app.agents.notification import agent as agent_module
from app.agents.notification.agent import NotificationResult, run_notification_agent
from app.agents.notification.parser import (
    NotificationEmail,
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
            NotificationEmail(subject="[P1] payments-api incident resolved", body="<p>root cause fixed</p>")
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
    assert captured["subject"] == "[P1] payments-api incident resolved"
    assert captured["html_body"] == "<p>root cause fixed</p>"


def test_llm_prompt_is_composed_from_report_fields(monkeypatch):
    monkeypatch.setattr(agent_module, "get_current_oncall", lambda: _oncall())
    fake_agent = _FakeAgent(NotificationEmail(subject="s", body="<p>b</p>"))
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


def test_send_failure_returns_error_result(monkeypatch):
    monkeypatch.setattr(agent_module, "get_current_oncall", lambda: _oncall())
    monkeypatch.setattr(
        agent_module,
        "create_structured_agent",
        lambda **kwargs: _FakeAgent(NotificationEmail(subject="s", body="<p>b</p>")),
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


def test_parser_raises_on_missing_structured_response():
    with pytest.raises(TypeError, match="structured_response"):
        parse_notification_response({"messages": []})


def test_parser_raises_on_wrong_type():
    with pytest.raises(TypeError, match="structured_response"):
        parse_notification_response({"structured_response": {"not": "a model"}})