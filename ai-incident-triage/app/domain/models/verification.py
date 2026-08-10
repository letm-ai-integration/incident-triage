from typing import List, Optional
from pydantic import BaseModel, Field

class VerificationResult(BaseModel):
    is_resolved: bool
    resolution_evidence: Optional[str] = None
    needs_reinvestigation: bool
    reinvestigation_hints: List[str] = Field(default_factory=list)
