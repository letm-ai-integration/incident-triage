"""Tests for the deterministic priority-floor rule."""
from datetime import UTC, datetime

import pytest

from app.domain.enums.environment import Environment
from app.domain.enums.priority import Priority
from app.domain.models.incident import Incident
from app.rules.classification import (
    compute_rule_based_priority,
    most_urgent,
    priority_rank,
)


def _incident(service: str, environment: Environment, description: str, raw_logs=None) -> Incident:
    return Incident(
        incident_id="INC-1",
        title="test incident",
        description=description,
        source="test",
        service=service,
        environment=environment,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        raw_logs=raw_logs or [],
    )


def test_production_login_error_is_p1():
    incident = _incident("login", Environment.PRODUCTION, "users cannot authenticate")
    incident = incident.model_copy(update={"raw_logs": ["AuthenticationException: token expired"]})
    assert compute_rule_based_priority(incident) == Priority.P1


def test_qa_login_error_is_not_p1():
    incident = _incident("login", Environment.QA, "login broken")
    incident = incident.model_copy(update={"raw_logs": ["AuthenticationException: token expired"]})
    result = compute_rule_based_priority(incident)
    assert result != Priority.P1
    assert result == Priority.P2


def test_dev_login_error_is_not_p1():
    incident = _incident("login", Environment.DEVELOPMENT, "login broken")
    incident = incident.model_copy(update={"raw_logs": ["exception: null pointer"]})
    result = compute_rule_based_priority(incident)
    assert result != Priority.P1
    assert result == Priority.P2


def test_staging_non_critical_no_error_is_p4():
    incident = _incident("reporting-dashboard", Environment.STAGING, "dashboard slow to load")
    assert compute_rule_based_priority(incident) == Priority.P4


def test_production_non_critical_service_with_error_is_p2():
    incident = _incident("reporting-dashboard", Environment.PRODUCTION, "dashboard down")
    incident = incident.model_copy(update={"raw_logs": ["500 error rendering report"]})
    assert compute_rule_based_priority(incident) == Priority.P2


def test_production_no_error_signal_is_p3():
    incident = _incident(
        "notifications", Environment.PRODUCTION, "minor UI alignment issue in the banner"
    )
    assert compute_rule_based_priority(incident) == Priority.P3


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (Priority.P1, Priority.P3, Priority.P1),
        (Priority.P3, Priority.P1, Priority.P1),
        (Priority.P2, Priority.P2, Priority.P2),
    ],
)
def test_most_urgent(a, b, expected):
    assert most_urgent(a, b) == expected


def test_priority_rank_orders_p1_as_most_urgent():
    assert priority_rank(Priority.P1) < priority_rank(Priority.P2) < priority_rank(
        Priority.P3
    ) < priority_rank(Priority.P4)
