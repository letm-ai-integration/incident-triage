from pydantic import BaseModel, Field

from app.domain.enums import IncidentType, Priority, Team


class Classification(BaseModel):
    """Result of the classification step: category and severity."""

    category: IncidentType = IncidentType.UNKNOWN
    severity: Priority = Priority.P3
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""
    assigned_team: Team = Team.UNKNOWN
