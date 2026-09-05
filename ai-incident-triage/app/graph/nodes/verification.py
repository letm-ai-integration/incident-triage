# v2: verifies the resolution against the expected outcome.
#
# Unresolved results route back to investigation (retry loop, bounded by
# domain.constants.MAX_INVESTIGATION_RETRIES); resolved results route to
# notification (see router.route_after_verification). The node also keeps the
# ``IncidentReport.verification`` field in sync via ``model_copy``.
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from app.domain.constants import DEFAULT_CONFIDENCE_SCORE
from app.domain.enums.status import IncidentStatus
from app.domain.models.verification import VerificationResult
from app.graph.builder import get_deps
from app.graph.state import IncidentState


def verification_node(state: IncidentState, config: RunnableConfig | None = None) -> dict:
    """Verify the resolution and write the ``VerificationResult`` to state."""
    deps = get_deps(config)
    service = deps.get("verification_service", _default_verify)
    try:
        update = service(state, deps)
    except Exception as exc:
        update = {"errors": state.get("errors", []) + [f"verification failed: {exc}"]}
    update.setdefault("current_step", "verification")
    return update


def _default_verify(state: IncidentState, deps: dict) -> dict:
    """Fallback verification: resolved when root-cause confidence meets the
    threshold and an expected action exists."""
    root_cause = state.get("root_cause")
    expected = state.get("expected_outcome") or {}
    resolved = (
        root_cause is not None
        and root_cause.confidence_score >= DEFAULT_CONFIDENCE_SCORE
        and bool(expected.get("action"))
    )

    if resolved:
        result = VerificationResult(
            is_resolved=True,
            resolution_evidence=(
                f"Diagnosis verified: root-cause confidence {root_cause.confidence_score} "
                "meets the threshold and a runbook-recommended fix exists. No fix has "
                "been applied by this system; remediation is pending on-call action."
            ),
            needs_reinvestigation=False,
            reinvestigation_hints=[],
        )
    else:
        result = VerificationResult(
            is_resolved=False,
            resolution_evidence=None,
            needs_reinvestigation=True,
            reinvestigation_hints=[expected.get("action") or "Re-run investigation with additional data."],
        )

    update: dict = {
        "verification_result": result,
        "is_resolved": result.is_resolved,
        "investigation_status": (
            IncidentStatus.RESOLVED if result.is_resolved else IncidentStatus.UNRESOLVED
        ),
    }
    report = state.get("incident_report")
    if report is not None:
        update["incident_report"] = report.model_copy(update={"verification": result})
    return update
