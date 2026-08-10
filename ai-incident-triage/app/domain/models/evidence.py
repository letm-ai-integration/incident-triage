from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class Evidence(BaseModel):
    evidence_id: str
    source: str  # e.g., "log_analysis", "runbook", "kubernetes"
    finding: str
    severity: str
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[datetime] = None

class EvidenceCollection(BaseModel):
    items: List[Evidence] = Field(default_factory=list)
    summary: str
