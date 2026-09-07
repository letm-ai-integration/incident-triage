"""Phase 6 + Phase 8: mock-dataset integrity and grounding-rules coverage.

Phase 6 scope (``tests/data``):
* every file parses into the domain ``Incident`` model;
* incident IDs are unique across the dataset;
* the 11 new Phase 6 incidents (B-L) exist with required fields, a valid
  environment/priority, non-empty telemetry (their scenarios specify telemetry),
  and canonical JSON-object log lines with per-incident windows and increasing
  ``sequence`` values.

Phase 8 scope (master 8.8/8.9/8.10) -- automated validation of the dataset
itself:
* every ``metadata.runbook`` reference resolves to a real standalone runbook
  file heading;
* no incident's text references another incident's id (no cross-incident
  leakage in the data);
* log-line ``environment``/``service`` fields agree with the incident's own
  environment/service where present;
* the 12 in-scope incidents (INC-006 + B-L) never contain completion/fix
  wording (they are investigation/recommendation scenarios by design);
* log timestamps stay inside each incident's own window.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from app.domain.enums.environment import Environment
from app.domain.enums.priority import Priority
from app.domain.models.incident import Incident

INCIDENTS = Path(__file__).resolve().parents[2] / "data" / "incidents"
RUNBOOKS = Path(__file__).resolve().parents[2] / "runbooks"

PHASE6 = {
    "INC-MEM-5006": "container-memory-usage.json",
    "INC-OOM-5007": "pod-oomkilled-crashloop.json",
    "INC-RATELIMIT-5008": "downstream-rate-limit-5xx.json",
    "INC-DNS-5009": "dns-resolution-failures.json",
    "INC-DISK-5010": "disk-space-exhaustion.json",
    "INC-CACHE-5011": "cache-stampede-redis.json",
    "INC-AVAIL-5001": "service-availability-traffic-spike.json",
    "INC-KAFKA-5002": "kafka-consumer-lag.json",
    "INC-DB-5003": "db-deadlock.json",
    "INC-TLS-5004": "tls-certificate-expiration.json",
    "INC-AVAIL-5005": "readiness-probe-misconfig.json",
}

# The 12 Phase 8 in-scope incidents: INC-006 + the 11 B-L files. D is indexed
# by INC-RATELIMIT-5008, E by INC-DNS-5009, etc. (see loaders/_incident.py).
PHASE8_SCOPE = list(PHASE6) + ["INC-006"]

# Completion/fix wording that must NEVER appear in an in-scope incident's
# narrative+telemetry. Chosen to be completion-specific so degraded *states*
# like "read-only recovery mode" or "back-off restarting" don't false-positive.
_COMPLETION_RE = re.compile(
    r"\b(resolved|was resolved|is resolved|has been resolved|recovered|restored|"
    r"fixed|healthy again|now healthy|back to normal|restarted successfully)\b",
    re.IGNORECASE,
)


def _all_raw_incidents() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(INCIDENTS.glob("*.json"))]


def _incident_text(raw: dict) -> str:
    parts = [raw.get("description", ""), *raw.get("raw_logs", [])]
    parts.extend(str(a) for a in raw.get("raw_alerts", []))
    parts.extend(json.dumps(e) for e in raw.get("raw_events", []))
    parts.append(json.dumps(raw.get("raw_metrics", {})))
    return " ".join(parts)


def _log_objects(raw: dict) -> list[dict]:
    return [json.loads(line) for line in raw.get("raw_logs", []) if line]


def test_every_incident_file_parses_into_incident_model():
    for raw in _all_raw_incidents():
        Incident.model_validate(raw)


def test_incident_ids_are_unique():
    seen: dict[str, int] = {}
    for raw in _all_raw_incidents():
        seen[raw["incident_id"]] = seen.get(raw["incident_id"], 0) + 1
    dupes = {k: v for k, v in seen.items() if v > 1}
    assert not dupes, f"duplicate incident ids: {dupes}"


@pytest.mark.parametrize(
    "incident_id,filename",
    sorted(PHASE6.items()),
    ids=lambda v: v,
)
def test_phase6_incident_valid(incident_id: str, filename: str):
    raw = json.loads((INCIDENTS / filename).read_text(encoding="utf-8"))
    assert raw["incident_id"] == incident_id
    incident = Incident.model_validate(raw)

    # required fields present and typed
    assert incident.service
    assert incident.environment in {e for e in Environment}
    assert incident.priority_hint is not None
    assert incident.priority_hint in {p for p in Priority}

    # the scenario's own telemetry is present (metrics always; logs per scenario)
    assert incident.raw_metrics, f"{incident_id}: scenario specifies metrics"
    assert incident.raw_logs, f"{incident_id}: scenario specifies logs"


def test_phase6_log_lines_are_canonical_json_with_schema_fields():
    for filename in PHASE6.values():
        raw = json.loads((INCIDENTS / filename).read_text(encoding="utf-8"))
        for line in raw["raw_logs"]:
            obj = json.loads(line)
            assert obj["level"], filename
            assert obj["message"], filename
            assert obj["timestamp"], filename
            assert "sequence" in obj and "loggerName" in obj, filename


@pytest.mark.parametrize("filename", sorted(PHASE6.values()))
def test_phase6_logs_stay_in_incident_window_with_increasing_sequence(filename: str):
    raw = json.loads((INCIDENTS / filename).read_text(encoding="utf-8"))
    incident_ts = datetime.fromisoformat(raw["timestamp"])
    last_seq = 0
    for line in raw["raw_logs"]:
        obj = json.loads(line)
        line_ts = datetime.fromisoformat(obj["timestamp"])
        assert abs((line_ts - incident_ts).total_seconds()) <= 7200, filename
        assert obj["sequence"] > last_seq, f"{filename}: sequence not increasing"
        last_seq = obj["sequence"]


# ---------------------------------------------------------------------------
# Phase 8 (8.8 / 8.9 / 8.10): automated validation of the mock dataset
# ---------------------------------------------------------------------------


def test_every_runbook_reference_resolves_to_a_runbook_file():
    headings = {
        p.read_text(encoding="utf-8").splitlines()[0][2:]
        for p in RUNBOOKS.glob("*.md")
        if p.read_text(encoding="utf-8").splitlines()
    }
    unresolved = []
    for raw in _all_raw_incidents():
        ref = raw.get("metadata", {}).get("runbook")
        if ref and ref not in headings:
            unresolved.append((raw["incident_id"], ref))
    assert not unresolved, f"runbook references without a matching file: {unresolved}"


def test_no_cross_incident_references():
    raw_all = _all_raw_incidents()
    ids = {r["incident_id"] for r in raw_all}
    offenders = []
    for raw in raw_all:
        text = _incident_text(raw)
        for other in ids - {raw["incident_id"]}:
            if other in text:
                offenders.append((raw["incident_id"], other))
    assert not offenders, f"cross-incident id references in data: {offenders}"


@pytest.mark.parametrize("incident_id", sorted(PHASE8_SCOPE), ids=lambda v: v)
def test_in_scope_incidents_never_contain_completion_wording(incident_id: str):
    filename = next(p for p in INCIDENTS.glob("*.json")
                    if json.loads(p.read_text(encoding="utf-8"))["incident_id"] == incident_id)
    raw = json.loads(filename.read_text(encoding="utf-8"))
    assert not _COMPLETION_RE.search(_incident_text(raw)), (
        f"{incident_id}: completion/fix wording present in an "
        f"investigation-only scenario"
    )


@pytest.mark.parametrize("filename", sorted(PHASE6.values()), ids=lambda v: v)
def test_log_environment_and_service_match_incident_scope(filename: str):
    raw = json.loads((INCIDENTS / filename).read_text(encoding="utf-8"))
    incident = Incident.model_validate(raw)
    for obj in _log_objects(raw):
        env = obj.get("environment")
        if env:
            assert env.lower() == str(incident.environment.value).lower(), (
                f"{filename}: log env {env!r} != incident env {incident.environment.value}"
            )
        svc = obj.get("service")
        if svc:
            assert svc == incident.service, (
                f"{filename}: log service {svc!r} != incident service {incident.service}"
            )