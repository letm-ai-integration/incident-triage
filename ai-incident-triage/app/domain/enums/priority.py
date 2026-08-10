from enum import StrEnum


class Priority(StrEnum):
    """Incident severity levels used across the triage pipeline."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
