"""Deterministic priority-floor rule for the Classification Agent.

Rule-based priority is a floor, not the final answer: the HLD is explicit
that priority must not be decided by the LLM alone. The Classification
Agent's LLM pass may escalate above this floor but must never fall below
it (see app/agents/classification/agent.py's reconciliation step).
"""
from __future__ import annotations

from app.domain.enums.environment import Environment
from app.domain.enums.priority import Priority
from app.domain.models.incident import Incident

# Business-critical flows: an outage here in production is always P1.
# Placeholder set -- extend to match the real service catalog.
CRITICAL_SERVICES = {
    "login",
    "auth",
    "authentication",
    "checkout",
    "payment",
    "payments",
    "billing",
    "cart",
    "order",
    "orders",
}

_ERROR_KEYWORDS = {
    "exception",
    "error",
    "fatal",
    "critical",
    "crash",
    "outage",
    "unavailable",
    "timeout",
    "failed",
    "down",
    "5xx",
}

_PRIORITY_ORDER = [Priority.P1, Priority.P2, Priority.P3, Priority.P4]


def priority_rank(priority: Priority) -> int:
    """Lower rank = more urgent. Used to enforce the rule floor."""
    return _PRIORITY_ORDER.index(priority)


def most_urgent(a: Priority, b: Priority) -> Priority:
    return a if priority_rank(a) <= priority_rank(b) else b


def _is_critical_service(service: str) -> bool:
    service_lower = service.lower()
    return any(keyword in service_lower for keyword in CRITICAL_SERVICES)


def _has_error_signal(incident: Incident) -> bool:
    haystack = " ".join([incident.description, *incident.raw_logs]).lower()
    return any(keyword in haystack for keyword in _ERROR_KEYWORDS)


def compute_rule_based_priority(incident: Incident) -> Priority:
    """Priority floor from environment + affected service + error signal.

    Production incidents on a critical service with an active error/exception
    are P1. The same failure outside production (staging/UAT, QA, dev) is
    never P1 -- it floors one tier lower, still scaled by the same signals
    down to P4 for low-impact cases.
    """
    critical_service = _is_critical_service(incident.service)
    error_signal = _has_error_signal(incident)

    if incident.environment == Environment.PRODUCTION:
        if critical_service and error_signal:
            return Priority.P1
        if critical_service or error_signal:
            return Priority.P2
        return Priority.P3

    # STAGING (incl. UAT), QA, DEVELOPMENT
    if critical_service and error_signal:
        return Priority.P2
    if critical_service or error_signal:
        return Priority.P3
    return Priority.P4
