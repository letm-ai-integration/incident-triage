# Conditional routing.
#
# Router functions are PURE: they only inspect state fields already computed by
# a prior node and return the outcome key for the caller's path_map. No I/O, no
# side effects, no service/LLM calls. Decisions must compare against the enums
# in app/domain/enums/ (never raw strings) so routing cannot silently break on
# spelling/casing mismatches.
#
# v2 routing:
#   classification -> investigation | notification   (by Priority / IncidentType)
#   approval       -> verification | notification    (approved vs rejected)
#   verification   -> investigation | notification   (reinvestigate loop vs done)
from app.domain.constants import MAX_INVESTIGATION_RETRIES
from app.domain.enums.incident_type import IncidentType
from app.domain.enums.priority import Priority
from app.graph.state import IncidentState


def route_after_classification(state: IncidentState) -> str:
    """Decide whether the incident needs the full investigation pipeline.

    Returns ``"full_investigation"`` for anything that needs deeper triage
    (P1/P2, unknown type, or low confidence) and ``"auto_resolve"`` for trivial
    incidents that can be sent straight to notification.
    """
    classification = state.get("classification")
    if classification is None:
        return "auto_resolve"
    if classification.incident_type == IncidentType.UNKNOWN:
        return "full_investigation"
    if classification.priority in (Priority.P1, Priority.P2):
        return "full_investigation"
    if classification.priority == Priority.P4:
        return "auto_resolve"
    return "full_investigation"


def route_after_approval(state: IncidentState) -> str:
    """Route to verification when approved, or to the rejection notification."""
    approval = state.get("approval")
    if approval is not None and not approval.approved:
        return "rejected"
    return "approved"


def route_after_verification(state: IncidentState) -> str:
    """Route back to investigation when unresolved (retry loop) or to
    notification when resolved / retries are exhausted."""
    verification = state.get("verification_result")
    if verification is None or verification.is_resolved:
        return "completed"
    if state.get("retry_count", 0) < MAX_INVESTIGATION_RETRIES:
        return "reinvestigate"
    return "completed"


__all__ = [
    "route_after_classification",
    "route_after_approval",
    "route_after_verification",
]
