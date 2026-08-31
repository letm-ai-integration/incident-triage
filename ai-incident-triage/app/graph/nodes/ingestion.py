# v2: normalizes raw incident input into the domain ``Incident`` model.
#
# The node is a thin adapter: it pulls ``raw_input`` from state, delegates to
# ``deps["ingestion_service"]`` when one is injected, and otherwise falls back
# to ``_default_ingest`` (a placeholder until app/services/ingestion_service.py
# is implemented). It only writes fields declared on ``IncidentState``.
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
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
    except Exception as exc:  # noqa: BLE001 -- degrade, never kill the run
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


def _stable_metadata_id(raw: dict) -> str | None:
    """A stable identifier carried on ``raw_input[\"metadata\"]`` (e.g. ``scenario_id``).

    The mock/scenario incidents deliberately put their real identity here (and
    in some files only here), so this must be honoured before inventing an ID.
    """
    metadata = raw.get("metadata")
    if not isinstance(metadata, dict):
        return None
    for key in ("scenario_id", "incident_id", "id"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _reproducible_id(raw: dict) -> str:
    """A deterministic ID derived from the incident's stable input fields.

    When no explicit ID / scenario_id is supplied, re-running the same mock input
    must produce the same ID rather than a different random one each time, so we
    hash title + service + timestamp.
    """
    title = str(raw.get("title", "")).strip()
    service = str(raw.get("service", "")).strip()
    timestamp = str(raw.get("timestamp", "")).strip()
    digest = hashlib.sha256(f"{title}|{service}|{timestamp}".encode()).hexdigest()[:8]
    return f"INC-{digest}"


def _resolve_incident_id(raw: dict, state: IncidentState) -> str:
    """Pick the incident ID with the following priority:

    1. An explicit ``raw_input.incident_id``.
    2. An ID already carried on shared ``state``.
    3. A stable ``metadata`` identifier (``scenario_id``/``incident_id``/``id``).
    4. A *reproducible* ID derived from title+service+timestamp.
    5. Only if there is nothing at all to derive from, a random ``INC-<hex>``
       (last resort).
    """
    explicit = raw.get("incident_id")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    state_id = state.get("incident_id")
    if isinstance(state_id, str) and state_id.strip():
        return state_id.strip()
    scenario = _stable_metadata_id(raw)
    if scenario:
        return scenario
    # Reproducible by default: same mock input -> same ID.
    if any(str(raw.get(k, "")).strip() for k in ("title", "service", "timestamp")):
        return _reproducible_id(raw)
    # Last resort: nothing stable to derive from, fall back to a random ID.
    return f"INC-{uuid4().hex[:8]}"


def _default_ingest(state: IncidentState, deps: dict) -> dict:
    """Fallback ingestion: build an ``Incident`` from ``raw_input``."""
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
        raw_logs=raw.get("logs", []),
        raw_events=raw.get("events", []),
        raw_alerts=raw.get("alerts", []),
        raw_metrics=raw.get("metrics", {}),
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
