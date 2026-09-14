"""Locks in that the dedicated guardrail-demo sample incidents under
data/incidents/ actually trip the guardrail each one is named for -- so these
samples stay live demonstrations rather than silently rotting if the incident
JSON or the guardrail logic changes.

The citation-existence (schema_validation) guardrail is intentionally not
covered here: it depends on live LLM behavior (whether the RCA agent cites an
id that doesn't exist), not on deterministic incident content, so it can't be
locked in this way -- see tests/services/test_rca_report_service.py and
tests/guardrails/test_custom_backend.py for its deterministic coverage.
"""
import json
from pathlib import Path

from app.guardrails.pii_guard import check_pii
from app.guardrails.prompt_injection import check_prompt_injection
from app.guardrails.safety_guard import check_content_safety

INCIDENTS_DIR = Path(__file__).resolve().parents[2] / "data" / "incidents"


def _load(name: str) -> dict:
    return json.loads((INCIDENTS_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _assemble_ingestion_text(raw: dict) -> str:
    """Mirror app.graph.nodes.ingestion._run_input_guardrails' text assembly."""
    parts = [raw.get("title", ""), raw.get("description", ""), *raw.get("raw_logs", [])]
    parts.append(str(raw.get("raw_events", [])))
    parts.append(str(raw.get("raw_alerts", [])))
    return "\n".join(parts)


def test_pii_sample_incident_triggers_pii_guardrail():
    raw = _load("pii-leaked-contact-info")
    result = check_pii("ingestion", _assemble_ingestion_text(raw))
    assert result.passed is False
    assert any("email" in f for f in result.findings)
    assert any("credit_card" in f for f in result.findings)


def test_prompt_injection_sample_incident_triggers_prompt_injection_guardrail():
    raw = _load("prompt-injection-attempt")
    result = check_prompt_injection("ingestion", _assemble_ingestion_text(raw))
    assert result.passed is False
    assert result.findings


def test_unsafe_content_sample_incident_triggers_safety_guardrail():
    raw = _load("unsafe-content-in-logs")
    result = check_content_safety("notification", raw["description"])
    assert result.passed is False
    assert result.findings
