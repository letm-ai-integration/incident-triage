# v2: normalizes raw incident input into the domain ``Incident`` model.
#
# The node is a thin adapter: it pulls ``raw_input`` from state, delegates to
# ``deps["ingestion_service"]`` when one is injected, and otherwise falls back
# to ``_default_ingest`` (a placeholder until app/services/ingestion_service.py
# is implemented). It only writes fields declared on ``IncidentState``.
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
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


def ingestion_node(state: IncidentState, config: Optional[RunnableConfig] = None) -> dict:
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


def _default_ingest(state: IncidentState, deps: dict) -> dict:
    """Fallback ingestion: build an ``Incident`` from ``raw_input``."""
    raw = state.get("raw_input") or {}
    incident = Incident(
        incident_id=raw.get("incident_id")
        or state.get("incident_id")
        or f"INC-{uuid4().hex[:8]}",
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


def _parse_priority(value: Any) -> Optional[Priority]:
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
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)
