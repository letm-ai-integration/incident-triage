"""Phase 6: canonical ``raw_*`` telemetry schema ingestion.

The ``Incident`` model carries ``raw_logs`` / ``raw_events`` / ``raw_alerts`` /
``raw_metrics``. Phase 6 standardises ingestion on those keys so rich-schema
incidents (INC-006 and the B-L set) no longer lose their telemetry, while the
legacy ``logs`` / ``events`` / ``alerts`` / ``metrics`` keys keep working for
older incident files.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.domain.enums.status import IncidentStatus
from app.domain.models.incident import Incident
from app.graph.nodes.ingestion import _default_ingest, ingestion_node
from app.graph.state import IncidentState

INCIDENTS = Path(__file__).resolve().parents[2] / "data" / "incidents"


def _load(name: str) -> dict:
    return json.loads((INCIDENTS / name).read_text(encoding="utf-8"))


def _state(raw: dict) -> IncidentState:
    return {"raw_input": raw}  # type: ignore[typeddict-item]


def _incident(raw: dict) -> Incident:
    return _default_ingest(_state(raw), {})["incident"]


def test_inc006_raw_telemetry_now_ingests():
    """INC-006 carries telemetry under raw_* keys only; it must not be empty."""
    inc = _incident(_load("database-connection-failure.json"))
    assert inc.raw_logs
    assert inc.raw_events
    assert inc.raw_alerts
    assert inc.raw_metrics
    assert "HikariPool-1" in inc.raw_logs[1]


def test_legacy_keys_still_work_as_fallback():
    """Pre-Phase-6 files use logs/events/alerts/metrics; those must map over."""
    raw = {
        "title": "t",
        "service": "s",
        "timestamp": "2026-01-01T00:00:00Z",
        "logs": ["legacy log line"],
        "events": [{"type": "deployment"}],
        "alerts": [{"name": "x"}],
        "metrics": {"cpu": 1},
    }
    inc = _incident(raw)
    assert inc.raw_logs == ["legacy log line"]
    assert inc.raw_events == [{"type": "deployment"}]
    assert inc.raw_alerts == [{"name": "x"}]
    assert inc.raw_metrics == {"cpu": 1}


def test_raw_keys_win_when_both_present():
    raw = {
        "title": "t",
        "service": "s",
        "timestamp": "2026-01-01T00:00:00Z",
        "logs": ["legacy"],
        "raw_logs": ["canonical"],
    }
    inc = _incident(raw)
    assert inc.raw_logs == ["canonical"]


def test_missing_telemetry_stays_empty():
    raw = {
        "title": "t",
        "service": "s",
        "timestamp": "2026-01-01T00:00:00Z",
    }
    inc = _incident(raw)
    assert inc.raw_logs == []
    assert inc.raw_metrics == {}


def test_prompt_injection_incident_is_quarantined():
    update = ingestion_node(_state(_load("prompt-injection-attempt.json")))
    assert update["quarantined"] is True
    assert update["investigation_status"] == IncidentStatus.ESCALATED
    checks = {f["check"] for f in update["guardrail_findings"]}
    assert "check_prompt_injection" in checks


def test_pii_incident_is_quarantined():
    update = ingestion_node(_state(_load("pii-leaked-contact-info.json")))
    assert update["quarantined"] is True
    checks = {f["check"] for f in update["guardrail_findings"]}
    assert "check_pii" in checks


def test_unsafe_content_incident_is_quarantined():
    update = ingestion_node(_state(_load("unsafe-content-in-logs.json")))
    assert update["quarantined"] is True
    checks = {f["check"] for f in update["guardrail_findings"]}
    assert "check_content_safety" in checks


def test_clean_incident_is_not_quarantined():
    update = ingestion_node(_state(_load("database-connection-failure.json")))
    assert update["quarantined"] is False


def test_domain_guardrail_flags_missing_description():
    raw = {
        "title": "t",
        "service": "s",
        "description": "",
        "timestamp": "2026-01-01T00:00:00Z",
    }
    update = ingestion_node(_state(raw))
    assert update["quarantined"] is False  # domain findings never quarantine
    domain_findings = [f for f in update["guardrail_findings"] if f["check"] == "check_domain_consistency"]
    assert domain_findings
    assert any("description" in msg for msg in domain_findings[0]["findings"])


def test_domain_guardrail_flags_invalid_priority_hint():
    raw = {
        "title": "t",
        "service": "s",
        "description": "d",
        "priority_hint": "P9",
        "timestamp": "2026-01-01T00:00:00Z",
    }
    update = ingestion_node(_state(raw))
    domain_findings = [f for f in update["guardrail_findings"] if f["check"] == "check_domain_consistency"]
    assert domain_findings
    assert any("priority_hint" in msg for msg in domain_findings[0]["findings"])