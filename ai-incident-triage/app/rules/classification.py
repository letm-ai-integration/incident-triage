"""Keyword-based classification rules used by the classification agent.

These rules provide a deterministic fallback that can be combined with LLM
classification. Keep business rules here, not in the graph builder.
"""

from app.domain.enums import IncidentType, Priority

KEYWORD_CATEGORY_MAP: dict[IncidentType, tuple[str, ...]] = {
    IncidentType.DATABASE: (
        "database",
        "db ",
        "sql",
        "query",
        "timeout",
        "connection pool",
    ),
    IncidentType.INFRASTRUCTURE: (
        "pod",
        "kubernetes",
        "deployment",
        "node",
        "cluster",
        "cpu",
        "memory",
        "disk",
    ),
    IncidentType.NETWORK: ("network", "latency", "dns", "dns", "routing", "5xx", "503"),
    IncidentType.APPLICATION: (
        "application",
        "api",
        "endpoint",
        "service",
        "http",
        "500",
    ),
    IncidentType.SECURITY: (
        "auth",
        "unauthorized",
        "breach",
        "attack",
        "permission",
        "access",
    ),
}

KEYWORD_SEVERITY_MAP: dict[Priority, tuple[str, ...]] = {
    Priority.P1: ("down", "outage", "critical", "data loss", "p1", "production down"),
    Priority.P2: ("degraded", "partial", "slow", "elevated error", "p2"),
    Priority.P3: ("minor", "cosmetic", "p3", "low impact"),
}


def classify_incident(title: str, description: str) -> tuple[IncidentType, Priority]:
    """Return (category, severity) based on keyword heuristics."""
    text = f"{title}\n{description}".lower()

    category = IncidentType.UNKNOWN
    for category_candidate, keywords in KEYWORD_CATEGORY_MAP.items():
        if any(keyword in text for keyword in keywords):
            category = category_candidate
            break

    severity = Priority.P3
    for severity_candidate, keywords in KEYWORD_SEVERITY_MAP.items():
        if any(keyword in text for keyword in keywords):
            severity = severity_candidate
            break

    return category, severity
