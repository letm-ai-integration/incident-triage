"""Tests for the Classification Agent's rule-floor reconciliation.

The LLM call itself is mocked -- these tests never make network calls.
"""
from datetime import UTC, datetime

import pytest

from app.agents.classification import agent as agent_module
from app.agents.classification.agent import classify_incident
from app.agents.classification.parser import parse_classification_response
from app.domain.enums.environment import Environment
from app.domain.enums.incident_type import IncidentType
from app.domain.enums.priority import Priority
from app.domain.models.classification import ClassificationResult
from app.domain.models.incident import Incident


def _incident(service="login", environment=Environment.PRODUCTION) -> Incident:
    return Incident(
        incident_id="INC-1",
        title="test incident",
        description="users cannot log in",
        source="test",
        service=service,
        environment=environment,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        raw_logs=["AuthenticationException: token expired"],
    )


def _llm_result(priority: Priority) -> ClassificationResult:
    return ClassificationResult(
        incident_type=IncidentType.APPLICATION,
        priority=priority,
        confidence=0.9,
        reasoning="mock reasoning",
        agrees_with_rule=True,
    )


class _FakeAgent:
    def __init__(self, structured_response):
        self._structured_response = structured_response
        self.invoked_with = None

    def invoke(self, payload):
        self.invoked_with = payload
        return {"structured_response": self._structured_response}


def test_llm_cannot_downgrade_below_rule_floor(monkeypatch):
    # Production + login + error -> rule floor is P1, but the LLM says P3.
    fake_agent = _FakeAgent(_llm_result(Priority.P3))
    monkeypatch.setattr(agent_module, "create_structured_agent", lambda **kwargs: fake_agent)

    result = classify_incident(_incident())

    assert result.priority == Priority.P1
    assert result.rule_based_priority == Priority.P1
    assert result.agrees_with_rule is False


def test_llm_can_escalate_above_rule_floor(monkeypatch):
    # QA + login + error -> rule floor is P2, but the LLM says P1.
    fake_agent = _FakeAgent(_llm_result(Priority.P1))
    monkeypatch.setattr(agent_module, "create_structured_agent", lambda **kwargs: fake_agent)

    result = classify_incident(_incident(environment=Environment.QA))

    assert result.priority == Priority.P1
    assert result.rule_based_priority == Priority.P2
    assert result.agrees_with_rule is False


def test_llm_agreeing_with_floor_is_recorded(monkeypatch):
    fake_agent = _FakeAgent(_llm_result(Priority.P1))
    monkeypatch.setattr(agent_module, "create_structured_agent", lambda **kwargs: fake_agent)

    result = classify_incident(_incident())

    assert result.priority == Priority.P1
    assert result.agrees_with_rule is True


def test_parser_raises_on_missing_structured_response():
    with pytest.raises(TypeError, match="structured_response"):
        parse_classification_response({"messages": []})


def test_parser_raises_on_wrong_type():
    with pytest.raises(TypeError, match="structured_response"):
        parse_classification_response({"structured_response": {"not": "a model"}})
