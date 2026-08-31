"""Tests for the RCA report service's citation-existence guardrail.

The RCA agent's LLM call is mocked -- these tests only exercise the
guardrail wiring, not the agent itself.
"""
from datetime import UTC, datetime

from app.domain.enums.environment import Environment
from app.domain.enums.incident_type import IncidentType
from app.domain.enums.priority import Priority
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.incident import Incident
from app.domain.models.root_cause import RootCauseAnalysis
from app.services import rca_report_service as service_module
from app.services.rca_report_service import rca_report_service


def _incident() -> Incident:
    return Incident(
        incident_id="INC-1",
        title="payments-api errors",
        description="500s on checkout",
        source="pagerduty",
        service="payments-api",
        environment=Environment.PRODUCTION,
        timestamp=datetime.now(UTC),
    )


def _classification() -> ClassificationResult:
    return ClassificationResult(
        incident_type=IncidentType.APPLICATION,
        priority=Priority.P1,
        confidence=0.9,
        reasoning="mock reasoning",
        affected_services=["payments-api"],
        agrees_with_rule=True,
    )


def _evidence() -> Evidence:
    return Evidence(evidence_id="ev-1", source="log_analysis", finding="connection pool exhausted", severity="ERROR")


def _state(evidence, hypotheses):
    return {
        "incident": _incident(),
        "incident_id": "INC-1",
        "classification": _classification(),
        "evidence": evidence,
        "hypotheses": hypotheses,
    }


def test_citation_existence_guardrail_passes_for_known_evidence(monkeypatch):
    evidence = [_evidence()]
    primary = Hypothesis(
        hypothesis_id="H1",
        description="pool exhaustion",
        confidence=0.9,
        supporting_evidence=["ev-1"],
        label=HypothesisLabel.LIKELY,
    )
    root_cause = RootCauseAnalysis(primary_cause=primary, confidence_score=0.9)
    monkeypatch.setattr(service_module, "generate_root_cause_analysis", lambda *a, **k: root_cause)

    result = rca_report_service(_state(evidence, [primary]), {})

    assert result["guardrail_findings"] == []


def test_citation_existence_guardrail_flags_hallucinated_evidence_id(monkeypatch):
    evidence = [_evidence()]
    primary = Hypothesis(
        hypothesis_id="H1",
        description="pool exhaustion",
        confidence=0.9,
        supporting_evidence=["ev-does-not-exist"],
        label=HypothesisLabel.LIKELY,
    )
    root_cause = RootCauseAnalysis(primary_cause=primary, confidence_score=0.9)
    monkeypatch.setattr(service_module, "generate_root_cause_analysis", lambda *a, **k: root_cause)

    result = rca_report_service(_state(evidence, [primary]), {})

    assert len(result["guardrail_findings"]) == 1
    finding = result["guardrail_findings"][0]
    assert finding["node"] == "rca_report"
    assert finding["passed"] is False
    assert any("ev-does-not-exist" in f for f in finding["findings"])
