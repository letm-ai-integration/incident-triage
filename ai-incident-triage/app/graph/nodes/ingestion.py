# v2: normalizes raw incident input into the domain ``Incident`` model.
#
# The node is a thin adapter: it pulls ``raw_input`` from state, delegates to
# ``deps["ingestion_service"]`` when one is injected, and otherwise falls back
# to ``_default_ingest`` (a placeholder until app/services/ingestion_service.py
# is implemented). It only writes fields declared on ``IncidentState``.
from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig

from app.domain.enums.environment import Environment
from app.domain.enums.priority import Priority
from app.domain.enums.status import IncidentStatus
from app.domain.models.incident import Incident
from app.graph.builder import get_deps
from app.graph.state import IncidentState
from app.guardrails.pii_guard import check_pii
from app.guardrails.prompt_injection import check_prompt_injection


def ingestion_node(state: IncidentState, config: RunnableConfig | None = None) -> dict:
    """Normalize raw input into an ``Incident`` and seed workflow bookkeeping."""
    deps = get_deps(config)
    service = deps.get("ingestion_service", _default_ingest)
    try:
        update = service(state, deps)
    except Exception as exc:
        update = {"errors": state.get("errors", []) + [f"ingestion failed: {exc}"]}
    update.setdefault("current_step", "ingestion")

    incident = update.get("incident")
    if incident is not None:
        findings = _run_input_guardrails(incident)
        if findings:
            update["guardrail_findings"] = state.get("guardrail_findings", []) + findings

    return update


def _run_input_guardrails(incident: Incident) -> list[dict]:
    """Prompt-injection + PII checks on the raw incident (HLD §14.1, §31 --
    defense-in-depth alongside the "untrusted data" framing in every agent
    prompt; does not block ingestion).
    """
    text = "\n".join(
        [
            incident.title,
            incident.description,
            *incident.raw_logs,
            str(incident.raw_events),
            str(incident.raw_alerts),
        ]
    )
    findings: list[dict] = []
    for check in (check_prompt_injection, check_pii):
        result = check("ingestion", text)
        if not result.passed:
            findings.append(
                {
                    "node": result.node_name,
                    "check": check.__name__,
                    "passed": result.passed,
                    "findings": result.findings,
                }
            )
    return findings


def _resolve_incident_id(raw: dict[str, Any], state: IncidentState) -> str:
    """Assign the incident's identity with an explicit, stable-first priority.

    1. Explicit ``incident_id`` in the raw input wins.
    2. An already-assigned ``incident_id`` in graph state wins.
    3. A stable identifier inside ``metadata`` (``scenario_id`` -- what the mock
       incidents use -- or ``incident_id``/``id``) is the incident's real
       identity and is used instead of minting a new one.
    4. Otherwise derive a *reproducible* id from title + service + timestamp so
       re-running the same input twice produces the same id.
    5. Pure-random generation is the last-resort fallback only.
    """
    if raw.get("incident_id"):
        return str(raw["incident_id"])
    if state.get("incident_id"):
        return str(state["incident_id"])
    metadata = raw.get("metadata") or {}
    if isinstance(metadata, dict):
        for key in ("scenario_id", "incident_id", "id"):
            if metadata.get(key):
                return str(metadata[key])
    # Reproducible fallback: hash the identity-defining fields (NOT wall-clock
    # time), so the same input maps to the same id on every run.
    basis = "|".join(
        str(raw.get(field) or "") for field in ("title", "service", "timestamp")
    )
    if basis.strip("|-"):
        return f"INC-{sha256(basis.encode('utf-8')).hexdigest()[:8]}"
    # Last resort: genuinely unknown origin -- random, clearly not stable.
    return f"INC-{uuid4().hex[:8]}"


def _default_ingest(state: IncidentState, deps: dict) -> dict:
    """Fallback ingestion: build an ``Incident`` from ``raw_input``.

    Accepts BOTH log/alert/event key conventions so every mock incident file
    flows through identically: the ``logs``/``events``/``alerts``/``metrics``
    style (legacy mock files) and the ``raw_logs``/``raw_events``/``raw_alerts``/
    ``raw_metrics`` style (INC-006 and the expanded incident set). Before this
    dual read, files using the ``raw_*`` keys had their data silently dropped
    here.
    """
    raw = state.get("raw_input") or {}
    incident = Incident(
        incident_id=_resolve_incident_id(raw, state),
        title=raw.get("title", "Untitled incident"),
        description=raw.get("description", ""),
        source=raw.get("source", "unknown"),
        service=raw.get("service", "unknown"),
        environment=_parse_environment(raw.get("environment")),
        priority_hint=_parse_priority(raw.get("priority_hint")),
        tags=raw.get("tags", []),
        timestamp=_parse_timestamp(raw.get("timestamp")),
        raw_logs=raw.get("raw_logs") or raw.get("logs") or [],
        raw_events=raw.get("raw_events") or raw.get("events") or [],
        raw_alerts=raw.get("raw_alerts") or raw.get("alerts") or [],
        raw_metrics=raw.get("raw_metrics") or raw.get("metrics") or {},
        metadata=raw.get("metadata", {}),
    )
    return {
        "incident": incident,
        "incident_id": incident.incident_id,
        "normalized_input": incident.model_dump(),
        "investigation_status": IncidentStatus.NEW,
    }


def _parse_environment(value: Any) -> Environment:
    if isinstance(value, Environment):
        return value
    if isinstance(value, str):
        try:
            return Environment(value)
        except ValueError:
            return Environment.DEVELOPMENT
    return Environment.DEVELOPMENT


def _parse_priority(value: Any) -> Priority | None:
    if isinstance(value, Priority):
        return value
    if isinstance(value, str):
        try:
            return Priority(value)
        except ValueError:
            return None
    return None


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.now(UTC)
    return datetime.now(UTC)
