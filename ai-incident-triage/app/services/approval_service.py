from app.domain.models import Approval, ApprovalStatus


class ApprovalService:
    """Records the human approval decision for the RCA report."""

    def record(
        self, approved: bool, reviewer: str = "", comments: str = ""
    ) -> Approval:
        status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        return Approval(status=status, reviewer=reviewer, comments=comments)
