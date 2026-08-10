from pydantic import BaseModel

from app.domain.models.incident import Incident
from app.domain.models.root_cause import RootCause


class IncidentReport(BaseModel):
    """Final incident report generated after investigation."""

    title: str = ""
    summary: str = ""
    incident: Incident | None = None
    root_cause: RootCause | None = None
