"""Phase 7: each new B-L incident name-resolves to its own runbook.

The name resolver must retrieve the correct top-level ``runbooks/*.md`` file
for every new incident (matching the exact display name), and each resolved
doc must carry a real ``## Solution`` so the final result can cite it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.investigation.runbook.resolver import (
    _section,
    load_runbooks,
    resolve_by_name,
)

INCIDENTS = Path(__file__).resolve().parents[3] / "data" / "incidents"
RUNBOOKS = Path(__file__).resolve().parents[3] / "runbooks"

# incident id -> (incident file, runbook file, runbook display-name prefix)
EXPECTED = {
    "INC-MEM-5006": ("container-memory-usage.json", "container-memory-limit.md", "Container Memory Limit"),
    "INC-OOM-5007": ("pod-oomkilled-crashloop.json", "oomkilled-crashloopbackoff.md", "OOMKilled / CrashLoopBackOff"),
    "INC-RATELIMIT-5008": ("downstream-rate-limit-5xx.json", "downstream-rate-limiting.md", "Downstream Rate Limiting"),
    "INC-DNS-5009": ("dns-resolution-failures.json", "coredns-degradation.md", "CoreDNS Degradation"),
    "INC-DISK-5010": ("disk-space-exhaustion.json", "disk-space-exhaustion.md", "Disk Space Exhaustion"),
    "INC-CACHE-5011": ("cache-stampede-redis.json", "cache-stampede.md", "Cache Stampede"),
    "INC-AVAIL-5001": ("service-availability-traffic-spike.json", "service-availability-traffic-spike.md", "Service Availability"),
    "INC-KAFKA-5002": ("kafka-consumer-lag.json", "kafka-consumer-lag.md", "Kafka Consumer Lag"),
    "INC-DB-5003": ("db-deadlock.json", "database-deadlock.md", "Database Deadlock"),
    "INC-TLS-5004": ("tls-certificate-expiration.json", "tls-certificate-expiration.md", "TLS Certificate Expiration"),
    "INC-AVAIL-5005": ("readiness-probe-misconfig.json", "readiness-probe-misconfiguration.md", "Readiness Probe Misconfiguration"),
}


def test_runbook_inventory_has_phase7_files():
    docs = load_runbooks()
    names = {doc.name for doc in docs}
    for _, md_file, _prefix in EXPECTED.values():
        assert (RUNBOOKS / md_file).is_file(), f"missing {md_file}"
        lines = (RUNBOOKS / md_file).read_text(encoding="utf-8").splitlines()
        display = lines[0]
        assert display.startswith("# ") and display[2:] in names


@pytest.mark.parametrize(
    "expected", sorted(EXPECTED.values(), key=lambda t: t[2]), ids=lambda t: t[2]
)
def test_incident_resolves_to_its_phase7_runbook(expected):
    incident_file, _md_file, prefix = expected
    raw = json.loads((INCIDENTS / incident_file).read_text(encoding="utf-8"))
    doc = resolve_by_name(raw["title"], raw["description"])
    assert doc is not None
    assert doc.name.startswith(prefix)
    assert doc.solution


@pytest.mark.parametrize("_,md_file,__", EXPECTED.values(), ids=lambda v: v)
def test_phase7_runbook_has_numbered_solution(_, md_file, __):
    lines = (RUNBOOKS / md_file).read_text(encoding="utf-8").splitlines()
    solution = _section(lines, "solution")
    assert solution
    assert "1." in solution