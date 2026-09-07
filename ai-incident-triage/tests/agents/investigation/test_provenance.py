"""Phase 2 verification: evidence provenance / grounding model.

Locks in the OBSERVED / REPORTED / CONTEXT / INFERRED distinction and the
evidence-availability guards that prevent empty telemetry from producing
"confirmed" findings. Runs in deterministic mode -- no LLM required.

Key guarantees under test:
- Evidence defaults to REPORTED, Hypothesis to INFERRED.
- Log/k8s findings are OBSERVED only when service-matching telemetry (attached
  raw logs/events or model-data documents for the incident's own service)
  actually exists.
- Unrelated services' retrieved documents never count as this incident's
  telemetry (no cross-incident contamination).
- Runbook evidence/hypotheses are always CONTEXT.
- An incident with zero telemetry but a keyword-rich description stays info and
  never claims log analysis "confirmed" anything.

Phase 8 additions:
- Every evidence item and hypothesis is stamped with the incident id +
  environment + time anchor (incident-scoping).
- Incident C's OOMKilled evidence is never reused for Incident B, and B's
  run never observes OOM-level degradation.
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from app.agents.investigation.kubernetes.agent import analyze_kubernetes_with_fallback
from app.agents.investigation.log_analysis.agent import analyze_logs_with_fallback
from app.agents.investigation.orchestrator import investigate
from app.domain.enums.environment import Environment
from app.domain.enums.provenance import EvidenceProvenance
from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis
from app.domain.models.incident import Incident

INCIDENTS = Path(__file__).resolve().parents[3] / "data" / "incidents"


def _incident(
    service: str,
    description: str,
    *,
    title: str = "",
    raw_logs: list[str] | None = None,
    raw_events: list[dict] | None = None,
) -> Incident:
    return Incident(
        incident_id="INC-PROV-TEST",
        title=title or f"{service} degradation",
        description=description,
        source="test",
        service=service,
        environment=Environment.PRODUCTION,
        timestamp=datetime(2026, 8, 6, 10, 20, tzinfo=UTC),
        raw_logs=raw_logs or [],
        raw_events=raw_events or [],
    )


def _incident_file(filename: str) -> Incident:
    raw = json.loads((INCIDENTS / filename).read_text(encoding="utf-8"))
    return Incident.model_validate(raw)


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


def test_evidence_defaults_to_reported():
    ev = Evidence(evidence_id="ev-1", source="log_analysis", finding="f", severity="info")
    assert ev.provenance == EvidenceProvenance.REPORTED


def test_hypothesis_defaults_to_inferred():
    hyp = Hypothesis(hypothesis_id="h-1", description="d", confidence=0.3, label="POSSIBLE")
    assert hyp.provenance == EvidenceProvenance.INFERRED


# ---------------------------------------------------------------------------
# Log agent grounding
# ---------------------------------------------------------------------------


def test_log_provenance_observed_when_service_matching_telemetry_retrieved():
    incident = _incident(
        "checkout-service",
        "checkouts failing while waiting on database connection pool 'HikariPool-1'",
        title="Database connection failure on checkout-service",
    )
    result = asyncio.run(analyze_logs_with_fallback(incident, None, None))
    ev = result.evidence[0]
    assert ev.provenance == EvidenceProvenance.OBSERVED
    assert ev.severity == "high"
    assert ev.raw_data.get("telemetry_signals")
    assert ev.raw_data.get("telemetry_available") is True


def test_log_with_zero_telemetry_is_reported_and_never_high():
    """The known bug: keyword-rich description + empty logs must NOT produce a
    'log analysis confirms ...' finding. severity stays info, provenance REPORTED."""
    incident = _incident(
        "graviton-scheduler",
        "connection timeout, failed requests, crash loop, exhausted pool behind spinning lock",
    )
    result = asyncio.run(analyze_logs_with_fallback(incident, None, None))
    ev = result.evidence[0]
    assert ev.severity == "info"
    assert ev.provenance == EvidenceProvenance.REPORTED
    assert ev.raw_data.get("telemetry_available") is False
    lowered = ev.finding.lower()
    assert "no" in lowered or "unavailable" in lowered


def test_unrelated_service_documents_not_counted_as_telemetry():
    """Cross-incident contamination: retrieval may surface OTHER services'
    documents for an unsynchronized service; those must not be treated as this
    incident's observed telemetry."""
    incident = _incident(
        "graviton-scheduler",
        "batch scheduling threads stopped draining the job queue",
    )
    result = asyncio.run(analyze_logs_with_fallback(incident, None, None))
    ev = result.evidence[0]
    assert ev.provenance == EvidenceProvenance.REPORTED
    assert ev.severity == "info"
    # If the RAG returned other services' docs, they must be flagged as such.
    assert "none belong to service" in ev.finding.lower() or "unavailable" in ev.finding.lower()


# ---------------------------------------------------------------------------
# Kubernetes agent grounding
# ---------------------------------------------------------------------------


def test_k8s_provenance_observed_from_own_events():
    incident = _incident(
        "payments",
        "payments pod restarting",
        raw_events=[
            {"reason": "CrashLoopBackOff Back-off restarting failed container payments-0"}
        ],
    )
    result = asyncio.run(analyze_kubernetes_with_fallback(incident, None, None))
    ev = result.evidence[0]
    assert ev.provenance == EvidenceProvenance.OBSERVED
    assert ev.severity == "medium"
    assert ev.raw_data.get("degraded") is True


def test_k8s_with_zero_telemetry_is_reported():
    incident = _incident("graviton-scheduler", "queue stalled")
    result = asyncio.run(analyze_kubernetes_with_fallback(incident, None, None))
    ev = result.evidence[0]
    assert ev.provenance == EvidenceProvenance.REPORTED
    assert ev.severity == "info"
    assert ev.raw_data.get("degraded") is False


# ---------------------------------------------------------------------------
# Orchestrator aggregation: runbook is always CONTEXT, synthesis INFERRED
# ---------------------------------------------------------------------------


def test_runbook_evidence_is_always_context():
    outcome = investigate(
        _incident(
            "checkout-service",
            "checkouts failing while waiting on database connection pool 'HikariPool-1'",
            title="Database connection failure on checkout-service",
            raw_logs=["ConnectionError: connection refused after timeout"],
        )
    )
    rb_ev = outcome.runbook_analysis
    assert rb_ev.source == "runbook"
    assert rb_ev.provenance == EvidenceProvenance.CONTEXT
    for hyp in outcome.hypotheses:
        if hyp.hypothesis_id != "hyp-1":
            assert hyp.provenance == EvidenceProvenance.CONTEXT


def test_synthesized_primary_hypothesis_is_inferred():
    outcome = investigate(
        _incident(
            "checkout-service",
            "checkouts failing while waiting on database connection pool 'HikariPool-1'",
            title="Database connection failure on checkout-service",
            raw_logs=["ConnectionError: connection refused after timeout"],
        )
    )
    primary = next(h for h in outcome.hypotheses if h.hypothesis_id == "hyp-1")
    assert primary.provenance == EvidenceProvenance.INFERRED
    # Every evidence item carries a known provenance.
    for ev in outcome.evidence:
        assert ev.provenance in {
            EvidenceProvenance.OBSERVED,
            EvidenceProvenance.REPORTED,
            EvidenceProvenance.CONTEXT,
            EvidenceProvenance.INFERRED,
        }


# ---------------------------------------------------------------------------
# Phase 8: incident-scoping of evidence/hypotheses
# ---------------------------------------------------------------------------


def test_every_evidence_and_hypothesis_is_stamped_with_incident_scope():
    incident = _incident_file("container-memory-usage.json")  # INC-MEM-5006
    outcome = investigate(incident)
    for ev in outcome.evidence:
        assert ev.incident_id == incident.incident_id
        assert ev.environment == incident.environment.value
        # Time anchor: evidence timestamps sit on the incident's own window
        # anchor (never a different date / another incident's timestamp).
        assert ev.timestamp == incident.timestamp
    for hyp in outcome.hypotheses:
        assert hyp.incident_id == incident.incident_id


def test_incident_c_oomkilled_evidence_never_leaks_to_incident_b():
    """Master 8.3: OOMKilled evidence from Incident C must never be reused for
    Incident B. B (memory saturation, no OOM kills, no k8s events) must observe
    no oom/crash-loop degradation; C (CrashLoopBackOff/OOMKilled events) must."""
    incident_b = _incident_file("container-memory-usage.json")
    incident_c = _incident_file("pod-oomkilled-crashloop.json")
    out_b, out_c = investigate(incident_b), investigate(incident_c)

    # Every piece of evidence is attributable to exactly one incident.
    for ev in out_b.evidence:
        assert ev.incident_id == "INC-MEM-5006"
        assert ev.environment == "STAGING"
    for ev in out_c.evidence:
        assert ev.incident_id == "INC-OOM-5007"
        assert ev.environment == "PRODUCTION"

    # B: no k8s events -> k8s evidence must NOT claim OOMKilled / crash-loop
    # degradation; C's crash-loop evidence must not appear under B at all.
    k8s_b = out_b.kubernetes_analysis
    assert k8s_b.raw_data.get("degraded") is False
    assert "oom" not in k8s_b.finding.lower()
    assert "crash" not in k8s_b.finding.lower()
    combined_b = " ".join(e.finding.lower() for e in out_b.evidence)
    assert "oomkilled" not in combined_b and "crashloop" not in combined_b

    # C: crash-loop events -> k8s evidence observes degradation.
    k8s_c = out_c.kubernetes_analysis
    assert k8s_c.raw_data.get("degraded") is True
    assert "crashloopbackoff" in k8s_c.finding.lower() or "oom" in k8s_c.finding.lower()

    # Each run answers only its own incident (object times differ; no shared
    # evidence items between the two outcomes).
    assert all(ev is not any_ev for ev in out_b.evidence for any_ev in out_c.evidence)

    # Time windows never mix: every item of B carries B's timestamp anchor and
    # every item of C carries C's (different incidents, different dates).
    assert incident_b.timestamp != incident_c.timestamp
    for ev_b in out_b.evidence:
        assert ev_b.timestamp == incident_b.timestamp
    for ev_c in out_c.evidence:
        assert ev_c.timestamp == incident_c.timestamp


def test_distinct_services_never_match_on_the_service_suffix():
    """Regression for the Phase 8.3 hole: the ``-service`` suffix is shared by
    every service name, so token-matching must require a distinctive token.
    ``content-service`` vs ``cart-service-6d7f4b`` (only share ``service``)
    must NOT be treated as the same workload -- otherwise Incident B would
    inherit cart-service's CrashLoop/OOMKilled documents as its own telemetry."""
    from app.agents.investigation.kubernetes.agent import _services_relate as k8s_relate
    from app.agents.investigation.log_analysis.agent import (
        _services_relate as log_relate,
    )

    pods = ["cart-service-6d7f4b-p9w2n", "cart-service-6d7f4b-t3r7c"]
    assert k8s_relate("content-service", pods) is False
    assert log_relate("content-service", pods) is False
    assert k8s_relate("product-catalog-service", pods) is False
    # Matching still works when a distinctive token is shared.
    assert k8s_relate("cart-service", pods) is True