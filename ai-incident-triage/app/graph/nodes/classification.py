# v2: classifies the incident into a category (IncidentType) AND severity
# (Priority) and writes both the full ``ClassificationResult`` model and the
# flattened state scalars. Absorbs the former v1 severity node.
from __future__ import annotations

from typing import Optional

from langchain_core.runnables import RunnableConfig

from app.domain.enums.incident_type import IncidentType
from app.domain.enums.priority import Priority
from app.domain.enums.status import IncidentStatus
from app.domain.enums.team import Team
from app.domain.models.classification import ClassificationResult
from app.graph.builder import get_deps
from app.graph.state import IncidentState

_TYPE_KEYWORDS = {
    IncidentType.KUBERNETES: (
        "kubernetes", "k8s", "pod", "container", "imagepullbackoff",
        "crashloopbackoff", "imagepull", "cluster", "node",
    ),
    IncidentType.DATABASE: (
        "database", "sql", "query", "connection pool", "db", "postgres",
        "mysql", "mongodb", "redis",
    ),
    IncidentType.NETWORK: (
        "network", "dns", "latency", "connectivity", "packet", "vpn",
        "load balancer",
    ),
    IncidentType.SECURITY: (
        "security", "unauthorized", "auth", "login", "breach", "malware", "ddos",
    ),
    IncidentType.PERFORMANCE: (
        "cpu", "memory", "slow", "performance", "high latency", "throttl",
        "saturation", "503", "http 503",
    ),
    IncidentType.INFRASTRUCTURE: (
        "infrastructure", "vm", "host", "disk", "storage", "hardware",
    ),
}

_TEAMS_BY_TYPE = {
    IncidentType.KUBERNETES: [Team.PLATFORM],
    IncidentType.DATABASE: [Team.DBA],
    IncidentType.NETWORK: [Team.NETWORK],
    IncidentType.SECURITY: [Team.SECURITY],
    IncidentType.APPLICATION: [Team.BACKEND],
    IncidentType.PERFORMANCE: [Team.SRE],
    IncidentType.INFRASTRUCTURE: [Team.SRE],
    IncidentType.UNKNOWN: [Team.ON_CALL],
}

_PRIORITY_KEYWORDS = {
    Priority.P1: ("critical", "outage", "down", "data loss", "breach", "severe", "crash"),
    Priority.P2: ("degraded", "timeout", "time out", "error rate", "slow", "unavailable"),
    Priority.P3: ("warning", "minor", "investigate", "flaky"),
}


def classification_node(state: IncidentState, config: Optional[RunnableConfig] = None) -> dict:
    """Produce a ``ClassificationResult`` (category + severity) for the incident."""
    deps = get_deps(config)
    service = deps.get("classification_service", _default_classify)
    try:
        update = service(state, deps)
    except Exception as exc:
        update = {"errors": state.get("errors", []) + [f"classification failed: {exc}"]}
    update.setdefault("current_step", "classification")
    return update


def _default_classify(state: IncidentState, deps: dict) -> dict:
    """Fallback classification: rule-based keyword matching over title/description."""
    incident = state.get("incident")
    text = f"{incident.title} {incident.description}".lower() if incident else ""
    incident_type = _detect_type(text)
    priority = _detect_priority(text, incident.priority_hint if incident else None)
    result = ClassificationResult(
        incident_type=incident_type,
        priority=priority,
        confidence=0.8,
        reasoning="Rule-based keyword classification (fallback while classification_service is unimplemented).",
        affected_services=[incident.service] if incident else [],
        suggested_teams=_TEAMS_BY_TYPE[incident_type],
        rule_based_priority=priority,
        agrees_with_rule=True,
    )
    return {
        "classification": result,
        "incident_type": result.incident_type,
        "severity": result.priority,
        "classification_confidence": result.confidence,
        "investigation_status": IncidentStatus.TRIAGING,
    }


def _detect_type(text: str) -> IncidentType:
    for incident_type, keywords in _TYPE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return incident_type
    return IncidentType.APPLICATION


def _detect_priority(text: str, hint: Optional[Priority]) -> Priority:
    for priority, keywords in _PRIORITY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return priority
    if hint is not None:
        return hint
    return Priority.P2
