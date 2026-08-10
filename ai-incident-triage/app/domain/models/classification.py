from typing import List, Optional
from pydantic import BaseModel, Field
from app.domain.enums.incident_type import IncidentType
from app.domain.enums.priority import Priority
from app.domain.enums.team import Team

class ClassificationResult(BaseModel):
    incident_type: IncidentType
    priority: Priority
    confidence: float
    reasoning: str
    affected_services: List[str] = Field(default_factory=list)
    suggested_teams: List[Team] = Field(default_factory=list)
    rule_based_priority: Optional[Priority] = None
    agrees_with_rule: bool
