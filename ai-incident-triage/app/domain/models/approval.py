from datetime import datetime
from pydantic import BaseModel

class ApprovalDecision(BaseModel):
    approved: bool
    reviewer: str
    comments: str
    timestamp: datetime
