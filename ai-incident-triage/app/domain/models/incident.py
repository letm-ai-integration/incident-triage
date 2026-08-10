from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.domain.enums import Environment, IncidentType, Priority, Status


class Incident(BaseModel):
    """A normalized incident ready for triage."""

    incident_id: str = Field(default="", description="Stable incident identifier.")
    title: str = ""
    description: str = ""
    source: str = ""
    environment: Environment = Environment.PRODUCTION
    incident_type: IncidentType = IncidentType.UNKNOWN
    priority: Priority = Priority.P3
    status: Status = Status.OPEN
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw: dict = Field(
        default_factory=dict, description="Unstructured original payload."
    )
