from enum import StrEnum

from pydantic import BaseModel


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Approval(BaseModel):
    """Human approval decision for the generated RCA report."""

    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewer: str = ""
    comments: str = ""
