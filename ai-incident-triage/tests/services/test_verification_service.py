"""Phase 4 verification: resolution is gated on external recovery evidence.

Locks in the decoupling: high RCA confidence + an expected action NEVER resolve
on their own. RESOLVED additionally requires positive recovery language in the
incident's raw telemetry (never the description, runbook text, or diagnosis),
and reinvestigation retries are accounted for exactly once per attempt here.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.constants import DEFAULT_CONFIDENCE_SCORE
from app.domain.enums.environment import Environment
from app.domain.enums.status import IncidentStatus
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.incident import Incident
from app.domain.models.root_cause import RootCauseAnalysis
from app.domain.models.verification import VerificationResult
from app.services.verification_service import verification_service


def _incident(**overrides) -> Incident:
    base: dict = {
        "incident_id": "INC-VF",
        "title": "t",
        "description": "incident under verification",
        "source": "test",
        "service": "svc",
        "environment": Environment.PRODUCTION,
        "timestamp": datetime(2026, 8, 1, tzinfo=UTC),
        "raw_logs": [],
        "raw_events": [],
        "raw_alerts": [],
        "raw_metrics": {},
    }
    base.update(overrides)
    return Incident(**base)


def _hypothesis(confidence: float = 0.8) -> Hypothesis:
    return Hypothesis(
        hypothesis_id="h1",
        description="connection pool exhaustion",
        confidence=confidence,
        supporting_evidence=[],
        contradicting_evidence=[],
        label=HypothesisLabel.LIKELY,
    )


def _state(incident: Incident, confidence: float = 0.8, action: str = "apply fix") -> dict:
    return {
        "incident": incident,
        "root_cause": RootCauseAnalysis(
            primary_cause=_hypothesis(confidence),
            contributing_factors=[],
            confidence_score=confidence,
        ),
        "expected_outcome": {"action": action},
    }


def _recovered_incident() -> Incident:
    return _incident(
        raw_logs=[
            "error rate returned to baseline after the rollout",
            "readiness probe ok, pod back to running",
        ],
    )


def test_high_confidence_plus_action_without_recovery_stays_unresolved():
    """The Phase 4 core: confidence + expected action must NOT resolve."""
    result = verification_service(_state(_incident()), {})
    assert result["is_resolved"] is False
    assert result["verification_result"].is_resolved is False
    assert result["verification_result"].resolution_evidence is None
    assert result["investigation_status"] == IncidentStatus.UNRESOLVED


def test_recovery_signal_with_high_confidence_resolves():
    result = verification_service(_state(_recovered_incident()), {})
    assert result["is_resolved"] is True
    assert result["verification_result"].needs_reinvestigation is False
    assert result["investigation_status"] == IncidentStatus.RESOLVED
    assert "error rate returned to baseline" in result["verification_result"].resolution_evidence


def test_recovery_signal_but_confidence_below_threshold_stays_unresolved():
    incident = _recovered_incident()
    low = DEFAULT_CONFIDENCE_SCORE - 0.1
    result = verification_service(_state(incident, confidence=low), {})
    assert result["is_resolved"] is False


def test_recovery_signal_but_no_expected_action_stays_unresolved():
    result = verification_service(_state(_recovered_incident(), action=""), {})
    assert result["is_resolved"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"raw_logs": ["5xx rate decreasing to baseline"]},
        {"raw_events": [{"reason": "latency p95 back to normal", "message": "latency normalized"}]},
        {"raw_alerts": [{"name": "QueueDrain", "message": "waiting queue drained and cleared"}]},
        {"raw_metrics": {"cpu_usage_pct": "cpu back to safe range"}},
        {"raw_logs": ["crash loop state cleared, pod back to running"]},
        {"raw_logs": ["autoscaler recovered after the fix"]},
        {"raw_logs": ["connectivity restored for checkout-service"]},
    ],
)
def test_positive_telemetry_signals_resolve(payload: dict):
    incident = _incident(**payload)
    result = verification_service(_state(incident), {})
    assert result["is_resolved"] is True
    assert "Recovery externally verified" in result["verification_result"].resolution_evidence


def test_recovery_words_in_description_do_not_count():
    """Recovery language in the description/runbook is diagnosis, not evidence."""
    incident = _incident(description="service recovered and returned to normal after the fix")
    result = verification_service(_state(incident), {})
    assert result["is_resolved"] is False


def test_degradation_markers_are_not_recovery():
    incident = _incident(
        raw_logs=["readiness probe failed, pod not ready"],
        raw_alerts=[{"name": "AuthServiceZeroHealthyEndpoints", "severity": "critical"}],
        raw_metrics={"readiness_failures": 4, "error_rate": "8.1/s"},
    )
    result = verification_service(_state(incident), {})
    assert result["is_resolved"] is False


def test_runbook_match_alone_never_resolves():
    state = _state(_incident())
    state["runbook_name"] = "kubernetes--auth-service--production"
    state["runbook_solution"] = "scale replicas and confirm recovery"
    result = verification_service(state, {})
    assert result["is_resolved"] is False


def test_unresolved_increments_retry_count_once():
    state = _state(_incident())
    result = verification_service(state, {})
    assert result["retry_count"] == 1
    result2 = verification_service({**state, "retry_count": 2}, {})
    assert result2["retry_count"] == 3


def test_resolved_does_not_increment_retry_count():
    state = _state(_recovered_incident())
    result = verification_service(state, {})
    assert "retry_count" not in result


def test_no_root_cause_never_resolves_recovery_or_not():
    incident = _recovered_incident()
    state = {
        "incident": incident,
        "root_cause": None,
        "expected_outcome": {"action": "n/a"},
    }
    result = verification_service(state, {})
    assert result["is_resolved"] is False


def test_syncs_incident_report_verification():
    from datetime import UTC, datetime

    from app.domain.enums.incident_type import IncidentType
    from app.domain.enums.priority import Priority
    from app.domain.models.classification import ClassificationResult
    from app.domain.models.evidence import EvidenceCollection
    from app.domain.models.report import IncidentReport

    incident = _incident()
    state = _state(incident)
    state["incident_report"] = IncidentReport(
        incident_id="INC-VF",
        classification=ClassificationResult(
            incident_type=IncidentType.APPLICATION,
            priority=Priority.P2,
            confidence=0.9,
            reasoning="t",
            affected_services=[],
            agrees_with_rule=True,
        ),
        evidence=EvidenceCollection(items=[], summary="No evidence collected."),
        hypotheses=[],
        root_cause=state["root_cause"],
        verification=VerificationResult(
            is_resolved=False, needs_reinvestigation=True
        ),
        created_at=datetime.now(UTC),
    )
    result = verification_service(state, {})
    assert result["incident_report"].verification.is_resolved is False