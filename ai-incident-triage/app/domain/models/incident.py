from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.domain.enums.environment import Environment
from app.domain.enums.priority import Priority

class Incident(BaseModel):
    incident_id: str
    title: str
    description: str
    source: str
    service: str
    environment: Environment
    priority_hint: Optional[Priority] = None
    tags: List[str] = Field(default_factory=list)
    timestamp: datetime
    raw_logs: List[str] = Field(default_factory=list)
    raw_events: List[Dict[str, Any]] = Field(default_factory=list)
    raw_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    raw_metrics: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
