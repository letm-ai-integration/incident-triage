from enum import StrEnum


class Status(StrEnum):
    """Lifecycle status of an incident through the triage workflow."""

    OPEN = "open"
    TRIAGING = "triaging"
    INVESTIGATING = "investigating"
    AWAITING_APPROVAL = "awaiting_approval"
    VERIFIED = "verified"
    RESOLVED = "resolved"
    CLOSED = "closed"
