"""Graph-node adapter for ``deps["verification_service"]``.

Phase 4: RCA confidence and resolution status are separate concepts. This
pipeline is investigate-only (no remediation executor), so RESOLVED requires
explicit, externally-supplied recovery evidence found in the incident's
telemetry payload -- a high confidence score, a runbook match, or an expected
action NEVER resolve on their own.

Recovery signals are detected strictly from incident telemetry (``raw_logs``,
``raw_events``, ``raw_alerts``, ``raw_metrics``) -- never from the incident
description, runbook text, or the diagnosis. Patterns only match positive
restoration language ("returned to baseline", "readiness ok", "normalized",
...), so degradation markers ("readiness probe failed", "ZeroHealthyEndpoints")
can never score as recovery.

The node also owns reinvestigation accounting: ``retry_count`` is incremented
here (and ONLY here) when a retry is requested, so the bounded loop in
``app/graph/router.py`` terminates even when the investigation step repeatedly
fails (previously the counter only grew on successful investigations).
"""
from __future__ import annotations

import re
from typing import Any

from app.domain.constants import DEFAULT_CONFIDENCE_SCORE
from app.domain.enums.status import IncidentStatus
from app.domain.models.verification import VerificationResult
from app.graph.state import IncidentState

# Positive restoration language only. Every pattern requires an explicit
# "back to healthy" signal; absence of these strings means "no recovery
# evidence" even when confidence is high.
_RECOVERY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"error\s*rate.{0,50}\b(?:return(?:ed|ing)?\s+to\s+(?:baseline|normal)|normaliz(?:ed|ing)?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:5(?:\d\d|xx)|429).{0,50}\b(?:decreasing|return(?:ed|ing)?\s+to\s+(?:baseline|normal))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:queue|waiting|pool).{0,50}\b(?:normaliz(?:ed|ing)?|drained|cleared|back\s+to\s+(?:baseline|normal))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:latency|p95|p99).{0,50}\b(?:normaliz(?:ed|ing)?|back\s+to\s+(?:baseline|normal))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:pod|deployment|crash\s*loop).{0,50}\b(?:back\s+to\s+running|crash\s+state\s+cleared|restarted\s+successfully|healthy)\b",
        re.IGNORECASE,
    ),
    re.compile(r"readiness.{0,50}\b(?:ok|healthy|pass(?:ed|ing)?)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:cpu|memory|disk).{0,50}\b(?:back\s+to\s+(?:safe|normal)|within\s+(?:safe\s+)?limits|normaliz(?:ed|ing)?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:has\s+)?recovered\b", re.IGNORECASE),
    re.compile(r"\brestored\s+services?\b", re.IGNORECASE),
    re.compile(r"\b(?:services?|normal\s+operations?|connectivity)\s+restored\b", re.IGNORECASE),
)


def verification_service(state: IncidentState, deps: dict[str, Any]) -> dict[str, Any]:
    """Resolve ONLY when the RCA basis is met AND recovery is externally observed.

    Returns the same state-update shape as the node's previous inline fallback,
    plus the retry accounting the reinvestigation loop relies on.
    """
    root_cause = state.get("root_cause")
    expected = state.get("expected_outcome") or {}
    rca_basis_met = bool(
        root_cause is not None
        and root_cause.confidence_score >= DEFAULT_CONFIDENCE_SCORE
        and bool(expected.get("action"))
    )
    recovery_signals = _detect_recovery_signals(state.get("incident"))

    if rca_basis_met and recovery_signals:
        result = VerificationResult(
            is_resolved=True,
            resolution_evidence=(
                f"Recovery externally verified from incident telemetry: {', '.join(recovery_signals)}. "
                f"RCA confidence {root_cause.confidence_score:.2f} meets the threshold with an "
                "expected remediation action; the fix itself was never applied by this system."
            ),
            needs_reinvestigation=False,
            reinvestigation_hints=[],
        )
    else:
        result = VerificationResult(
            is_resolved=False,
            resolution_evidence=None,
            needs_reinvestigation=True,
            reinvestigation_hints=[
                expected.get("action") or "Re-run investigation with additional data."
            ],
        )

    update: dict[str, Any] = {
        "verification_result": result,
        "is_resolved": result.is_resolved,
        "investigation_status": (
            IncidentStatus.RESOLVED if result.is_resolved else IncidentStatus.UNRESOLVED
        ),
    }
    if result.needs_reinvestigation:
        update["retry_count"] = state.get("retry_count", 0) + 1

    report = state.get("incident_report")
    if report is not None:
        update["incident_report"] = report.model_copy(update={"verification": result})
    return update


def _signal_text(incident: Any | None) -> str:
    """Flatten the incident's raw telemetry into one searchable string."""
    if incident is None:
        return ""
    parts: list[str] = [str(incident.raw_logs)]
    for events in (incident.raw_events, incident.raw_alerts):
        for item in events:
            if isinstance(item, dict):
                parts.append(str(item.get("message", "")))
                parts.append(str(item))
            else:
                parts.append(str(item))
    for key, value in (incident.raw_metrics or {}).items():
        parts.append(f"{key} {value}")
    return "\n".join(parts)


def _detect_recovery_signals(incident: Any | None) -> list[str] | None:
    """Return matched recovery-signal descriptors, or None when none present.

    ``None`` (as opposed to ``[]``) is the explicit "no recovery evidence"
    marker the resolution gate branches on.
    """
    text = _signal_text(incident)
    if not text.strip():
        return None
    matched: list[str] = []
    labels = (
        "error rate returned to baseline",
        "error/5xx rate decreasing or at baseline",
        "queue/waiting/pool normalized or cleared",
        "latency normalized",
        "pod/deployment healthy or crash state cleared",
        "readiness healthy",
        "cpu/memory/disk back to safe range",
        "explicit recovery observed",
        "service restored",
        "normal operations restored",
    )
    for pattern, label in zip(_RECOVERY_PATTERNS, labels):
        if pattern.search(text):
            matched.append(label)
    return matched or None