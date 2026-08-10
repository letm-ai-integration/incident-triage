from app.domain.models import Incident


class IngestionService:
    """Normalizes a raw incident payload into an :class:`Incident` model."""

    def normalize(self, payload: dict) -> Incident:
        incident = Incident.model_validate(payload)
        incident.incident_id = str(payload.get("incident_id") or incident.incident_id)
        return incident
