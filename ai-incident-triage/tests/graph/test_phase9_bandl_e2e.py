"""Phase 9: end-to-end fixture per new incident (B-L) over the mock pipeline.

Runs the full triage graph (deterministic fallbacks, no LLM) against each of
the 11 Phase 6 incidents and locks in the master's grounding guarantees at the
integration layer:

* investigate-only: every incident exits UNRESOLVED, notification NOTIFIED;
* every piece of evidence/hypothesis is stamped with the incident id +
  environment (+ time anchor) -- no cross-incident attribution;
* each incident's own Phase 7 runbook is retrieved and cited;
* the canonical Phase 5 report never says "resolved", remediation is always
  "Pending On-Call Action", and the narrative is substantive (>=5 lines);
* per-incident ground truth: OOMKilled evidence only ever under C, never B;
  CPU/traffic claims stay grounded; L's restart-count-0 is never read as
  instability.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.enums.status import IncidentStatus, NotificationStatus
from app.graph.workflow import triage_graph
from app.services.investigation_service import investigation_service
from app.services.notification_service import notification_service
from app.services.rca_report_service import render_markdown_report

INCIDENTS = Path(__file__).resolve().parents[2] / "data" / "incidents"
RECURSION_LIMIT = 50


def _run(raw_input: dict) -> dict:
    return triage_graph.invoke(
        {"raw_input": raw_input},
        config={
            "configurable": {
                "deps": {
                    "auto_approve": True,
                    "investigation_service": investigation_service,
                    "notification_service": notification_service,
                }
            },
            "recursion_limit": RECURSION_LIMIT,
        },
    )


def _load(name: str) -> dict:
    return json.loads((INCIDENTS / name).read_text(encoding="utf-8"))


# (filename, expected runbook prefix, k8s expectation)
# k8s expectations: (degraded, finding must contain, finding must NOT contain)
PHASE6_FIXTURES = {
    "container-memory-usage.json": ("Container Memory Limit", (False, "", "oomkilled|crashloop")),
    "pod-oomkilled-crashloop.json": ("OOMKilled / CrashLoopBackOff", (True, "oom|crashloop", "")),
    "downstream-rate-limit-5xx.json": ("Downstream Rate Limiting", None),
    "dns-resolution-failures.json": ("CoreDNS Degradation", None),
    "disk-space-exhaustion.json": ("Disk Space Exhaustion", None),
    "cache-stampede-redis.json": ("Cache Stampede", None),
    "service-availability-traffic-spike.json": ("Service Availability", (True, "restart|crash|traffic", "")),
    "kafka-consumer-lag.json": ("Kafka Consumer Lag", None),
    "db-deadlock.json": ("Database Deadlock", None),
    "tls-certificate-expiration.json": ("TLS Certificate Expiration", None),
    "readiness-probe-misconfig.json": (
        "Readiness Probe Misconfiguration",
        # restart-count-0: never read as instability -- degraded stays False and
        # the k8s finding must not claim crashes/restarts of the workload.
        (False, "", "crash|restart|unstable|flapping"),
    ),
}


def _k8s_evidence(result: dict):
    return next(e for e in result["evidence"] if e.source == "kubernetes")


def _all_evidence_text(result: dict) -> str:
    return " ".join(e.finding.lower() for e in result["evidence"])


@pytest.mark.parametrize(
    "fixture",
    sorted(PHASE6_FIXTURES.items()),
    ids=lambda kv: kv[0],
)
def test_phase6_incident_e2e_no_resolution_correct_runbook(fixture):
    filename, (expected_runbook, k8s_expectation) = fixture
    result = _run(_load(filename))
    incident = result["incident"]

    # investigate-only: never resolved; notification still fires
    assert result["is_resolved"] is False
    assert result["investigation_status"] == IncidentStatus.UNRESOLVED
    assert result["notification_status"] == NotificationStatus.NOTIFIED
    assert result["incident_report"] is not None

    # incident-scoping: all evidence + hypotheses belong to THIS incident only
    for ev in result["evidence"]:
        assert ev.incident_id == incident.incident_id
        assert ev.environment == incident.environment.value
        assert ev.timestamp == incident.timestamp
    for hyp in result["hypotheses"]:
        assert hyp.incident_id == incident.incident_id

    # the incident's own Phase 7 runbook is the one matched + cited
    assert result["runbook_name"]
    assert result["runbook_name"].startswith(expected_runbook)
    ok = result["runbook_solution"]
    assert ok

    # canonical Phase 5 markdown: structure, ≥5-line narrative, honest status
    markdown = render_markdown_report(result["incident_report"])
    lower = markdown.lower()
    assert "## incident summary" in lower
    assert "### incident overview" in lower
    assert "### root cause analysis" in lower
    assert "### recommended remediation" in lower
    assert "### investigation status" in lower
    overview = markdown.split("### Incident Overview", 1)[1].split("### Environment", 1)[0]
    bullets = [l for l in overview.splitlines() if l.startswith("**")]
    assert len(bullets) >= 5, "Overview narrative must genuinely explain the chain"
    assert "- **Remediation:** Pending On-Call Action" in markdown
    assert "resolved" not in lower
    assert not result.get("errors")

    # per-incident k8s ground truth (OOMKilled only under C; L not instability)
    if k8s_expectation is not None:
        degraded, must_have, must_not_have = k8s_expectation
        k8s = _k8s_evidence(result)
        assert k8s.raw_data.get("degraded") is degraded, (filename, k8s.finding)
        if must_have:
            assert any(w in k8s.finding.lower() for w in must_have.split("|")), (filename, k8s.finding)
        if must_not_have:
            assert not any(w in k8s.finding.lower() for w in must_not_have.split("|")), (filename, k8s.finding)

    # B never borrows C's OOMKilled/crash-loop language
    if filename == "container-memory-usage.json":
        assert "oomkilled" not in _all_evidence_text(result)
        assert "crashloop" not in _all_evidence_text(result)