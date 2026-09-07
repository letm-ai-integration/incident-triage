"""Phase 3 verification: deterministic claim validation & confidence calibration.

Locks in the claim-support rules (OOMKilled / CrashLoopBackOff / CPU saturation /
DB outage-vs-pool-exhaustion / recovery / runbook-only / empty-source) and the
confidence calibration that turns a finding into a penalty + downgraded wording.
Runs entirely deterministically -- no LLM, no vector store.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.enums.environment import Environment
from app.domain.enums.provenance import EvidenceProvenance
from app.domain.models.claim_validation import ClaimCategory
from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.incident import Incident
from app.domain.models.root_cause import RootCauseAnalysis
from app.services.evidence_service import validate_hypotheses
from app.services.hypothesis_service import calibrate_hypotheses, finalize_root_cause


def _incident(**overrides) -> Incident:
    base: dict = {
        "incident_id": "INC-CL",
        "title": "t",
        "description": "incident under validation",
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


def _h(description: str, h_id: str = "hyp-1", **overrides) -> Hypothesis:
    base: dict = {
        "hypothesis_id": h_id,
        "description": description,
        "confidence": 0.8,
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "label": HypothesisLabel.LIKELY,
    }
    base.update(overrides)
    return Hypothesis(**base)


def _finding(findings, category):
    return next(f for f in findings if f.category == category)


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


def test_oomkilled_claim_unsupported_without_signal():
    h = _h("checkout pods were repeatedly OOMKilled after capacity was added")
    findings = validate_hypotheses(_incident(), [], [h])
    f = _finding(findings, ClaimCategory.OOMKILLED)
    assert f.supported is False
    assert f.penalty == 0.15
    assert "no OOMKilled" in f.qualifier


def test_oomkilled_claim_supported_by_observed_signal():
    evidence = [
        Evidence(
            evidence_id="ev-k8s-1", source="kubernetes",
            finding="Pod killed with OOMKilled, exit code 137",
            severity="medium", provenance=EvidenceProvenance.OBSERVED,
        )
    ]
    h = _h("pods OOMKilled", supporting_evidence=["ev-k8s-1"])
    findings = validate_hypotheses(_incident(), evidence, [h])
    assert _finding(findings, ClaimCategory.OOMKILLED).supported is True


def test_crashloop_claim_unsupported_without_k8s_state():
    h = _h("auth pods are stuck in CrashLoopBackOff")
    findings = validate_hypotheses(_incident(), [], [h])
    f = _finding(findings, ClaimCategory.CRASHLOOPBACKOFF)
    assert f.supported is False
    assert f.penalty == 0.15
    assert "no matching Kubernetes state/events" in f.qualifier


def test_crashloop_claim_supported_by_attached_events():
    incident = _incident(raw_events=[{"reason": "CrashLoopBackOff restarting container"}])
    h = _h("pods CrashLoopBackOff")
    findings = validate_hypotheses(incident, [], [h])
    assert _finding(findings, ClaimCategory.CRASHLOOPBACKOFF).supported is True


def test_cpu_saturation_requires_cpu_metrics_not_heap():
    inc = _incident(raw_metrics={"jvm_heap_usage_pct": 95.0})
    h = _h("CPU saturation at 100% for the content api")
    findings = validate_hypotheses(inc, [], [h])
    f = _finding(findings, ClaimCategory.CPU_SATURATION)
    assert f.supported is False
    assert f.penalty == 0.15
    assert "no CPU metrics" in f.qualifier


def test_empty_metrics_cannot_confirm_cpu_or_traffic_claim():
    # Phase 9.2: with empty metrics (no cpu_usage_pct anywhere), a CPU/traffic
    # saturation claim must be flagged unsupported -- never metric-confirmed.
    h = _h("CPU saturated and traffic near capacity during the spike")
    findings = validate_hypotheses(_incident(), [], [h])
    f = _finding(findings, ClaimCategory.CPU_SATURATION)
    assert f.supported is False
    assert f.penalty == 0.15
    assert "no CPU metrics" in f.qualifier

    inc_cpu = _incident(raw_metrics={"cpu_usage_pct": 99.0})
    findings2 = validate_hypotheses(inc_cpu, [], [h])
    assert _finding(findings2, ClaimCategory.CPU_SATURATION).supported is True


def test_db_outage_downgraded_to_pool_exhaustion_without_penalty():
    evidence = [
        Evidence(
            evidence_id="ev-log-1", source="log_analysis",
            finding="connection pool exhausted for checkout-db, waiting threads blocking",
            severity="high", provenance=EvidenceProvenance.OBSERVED,
        )
    ]
    h = _h("the primary database is unreachable for checkout traffic", supporting_evidence=["ev-log-1"])
    findings = validate_hypotheses(_incident(), evidence, [h])
    f = _finding(findings, ClaimCategory.DB_OUTAGE)
    assert f.supported is False
    assert f.penalty == 0.0  # reword, not penalize -- pool telemetry is real
    assert "not a DB outage" in f.qualifier


def test_db_outage_unsupported_when_no_database_telemetry_at_all():
    h = _h("the database went down tonight")
    findings = validate_hypotheses(_incident(), [], [h])
    f = _finding(findings, ClaimCategory.DB_OUTAGE)
    assert f.supported is False
    assert f.penalty == 0.15


def test_recovery_claim_never_verified():
    h = _h("service recovered and returned to normal after the rollout")
    findings = validate_hypotheses(_incident(), [], [h])
    f = _finding(findings, ClaimCategory.RECOVERY)
    assert f.supported is False
    assert f.penalty == 0.10  # INFERRED claim about recovery penalized
    assert "no post-remediation recovery evidence" in f.qualifier


def test_runbook_context_claim_flagged_but_unpenalized():
    h = _h("runbook symptom section: latency spikes to p95", provenance=EvidenceProvenance.CONTEXT)
    findings = validate_hypotheses(_incident(), [], [h])
    f = _finding(findings, ClaimCategory.RUNBOOK_ONLY)
    assert f.supported is False
    assert f.penalty == 0.0
    assert "symptom not independently verified" in f.qualifier


def test_empty_source_evidence_penalized():
    evidence = [
        Evidence(
            evidence_id="ev-log-1", source="log_analysis",
            finding="no log evidence", severity="info",
            provenance=EvidenceProvenance.REPORTED,
            raw_data={"log_count": 0, "retrieved_documents": 0, "telemetry_available": False},
        )
    ]
    h = _h("error rate caused by a code bug", supporting_evidence=["ev-log-1"])
    findings = validate_hypotheses(_incident(), evidence, [h])
    f = _finding(findings, ClaimCategory.EMPTY_SOURCE)
    assert f.supported is False
    assert f.penalty == 0.15
    assert "telemetry unavailable" in f.qualifier


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


def test_calibrate_hypotheses_applies_penalty_and_downgrades_label():
    h = _h("pods CrashLoopBackOff with no k8s telemetry", supporting_evidence=["ev-k8s-1"])
    findings = validate_hypotheses(_incident(), [], [h])
    calibrated = calibrate_hypotheses([h], findings)
    assert calibrated[0].confidence == pytest.approx(0.65)  # 0.80 - 0.15
    assert calibrated[0].label == HypothesisLabel.POSSIBLE


def test_finalize_root_cause_qualifies_wording_and_caps_confidence():
    h = _h("OOMKilled without any memory telemetry", h_id="hyp-1")
    findings = validate_hypotheses(_incident(), [], [h])
    rca = RootCauseAnalysis(primary_cause=h, contributing_factors=[], confidence_score=0.8)
    finalized = finalize_root_cause(rca, findings, [h])

    assert finalized.primary_cause.confidence == pytest.approx(0.65)
    assert "reported OOMKilled" in finalized.primary_cause.description
    # POSSIBLE label (0.65) => shared ceiling is label-scaled (0.6 * 0.65)
    assert finalized.confidence_score == pytest.approx(0.65 * 0.6)
    assert finalized.claim_validation == findings


def test_finalize_root_cause_leaves_supported_rca_untouched():
    evidence = [
        Evidence(
            evidence_id="ev-log-1", source="log_analysis",
            finding="connection pool exhausted, connectivity ok",
            severity="high", provenance=EvidenceProvenance.OBSERVED,
        )
    ]
    h = _h("connection pool exhaustion under traffic", h_id="hyp-1", supporting_evidence=["ev-log-1"])
    findings = validate_hypotheses(_incident(raw_metrics={"db_pool_wait_queue_depth": 500}), evidence, [h])
    rca = RootCauseAnalysis(primary_cause=h, contributing_factors=[], confidence_score=0.8)
    finalized = finalize_root_cause(rca, findings, [h])
    assert finalized.primary_cause.confidence == pytest.approx(0.8)
    assert finalized.confidence_score == pytest.approx(0.8)


def test_multiple_categories_capped_penalty():
    h = _h(
        "OOMKilled CrashLoopBackOff and CPU saturation all at once, none observed",
        supporting_evidence=["ev-k8s-1"],
    )
    findings = validate_hypotheses(_incident(), [], [h])
    categories = {f.category for f in findings}
    assert ClaimCategory.OOMKILLED in categories
    assert ClaimCategory.CRASHLOOPBACKOFF in categories
    assert ClaimCategory.CPU_SATURATION in categories
    assert sum(f.penalty for f in findings) == 0.15 * 3
    calibrated = calibrate_hypotheses([h], findings)
    assert calibrated[0].confidence == pytest.approx(0.55)  # capped at -0.25


# ---------------------------------------------------------------------------
# Graph-node + service wiring
# ---------------------------------------------------------------------------


def test_default_rca_report_runs_claim_validation():
    from app.graph.nodes.rca_report import _default_rca_report

    incident = _incident()
    evidence = [
        Evidence(
            evidence_id="ev-log-1", source="log_analysis",
            finding="log retrieval unavailable", severity="info",
            provenance=EvidenceProvenance.REPORTED,
            raw_data={"telemetry_available": False},
        )
    ]
    h = _h(
        "pods CrashLoopBackOff after the deploy", h_id="hyp-1",
        supporting_evidence=["ev-log-1"],
    )
    state = {"incident": incident, "evidence": evidence, "hypotheses": [h], "investigation_summary": {}}
    update = _default_rca_report(state, {})

    assert update["claim_validation"]
    rc = update["root_cause"]
    assert rc.confidence_score < 0.8  # unsupported claim penalized
    assert "no matching Kubernetes state/events" in rc.primary_cause.description
    assert rc.claim_validation  # attached to the typed RCA


def test_rca_report_service_runs_claim_validation(monkeypatch):
    from app.domain.enums.incident_type import IncidentType
    from app.domain.enums.priority import Priority
    from app.domain.models.classification import ClassificationResult
    from app.services import rca_report_service as module

    evidence = [
        Evidence(
            evidence_id="ev-1", source="log_analysis",
            finding="connection pool exhausted under traffic", severity="high",
        )
    ]
    primary = _h(
        "pool exhaustion under traffic", h_id="H1",
        supporting_evidence=["ev-1"], confidence=0.9,
    )
    rca = RootCauseAnalysis(primary_cause=primary, contributing_factors=[], confidence_score=0.9)
    monkeypatch.setattr(module, "generate_root_cause_analysis", lambda *a, **k: rca)

    classification = ClassificationResult(
        incident_type=IncidentType.APPLICATION,
        priority=Priority.P1,
        confidence=0.9,
        reasoning="t",
        affected_services=["svc"],
        agrees_with_rule=True,
    )
    state = {
        "incident": _incident(),
        "incident_id": "INC-1",
        "classification": classification,
        "evidence": evidence,
        "hypotheses": [primary],
    }
    result = module.rca_report_service(state, {})

    assert "claim_validation" in result
    assert result["root_cause"].confidence_score == pytest.approx(0.9)  # fully supported
    assert result["root_cause"].claim_validation == []