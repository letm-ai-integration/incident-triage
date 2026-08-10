from enum import StrEnum


class IncidentType(StrEnum):
    """High level incident categories emitted by the classification node."""

    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"
    DATABASE = "database"
    NETWORK = "network"
    SECURITY = "security"
    UNKNOWN = "unknown"
