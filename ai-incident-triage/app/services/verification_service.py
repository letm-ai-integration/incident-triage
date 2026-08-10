from app.domain.models import Incident, Verification


class VerificationService:
    """Determines whether the incident is resolved based on the outcome data.

    A real integration would compare against the monitoring system; this stub
    reads a ``"resolved"`` flag from the raw payload. When unresolved, the graph
    re-investigates (the router sends it back to the investigation node).
    """

    def verify(self, incident: Incident) -> Verification:
        resolved = bool(incident.raw.get("resolved", False))
        return Verification(resolved=resolved, notes="mock outcome check")
