from enum import StrEnum


class Team(StrEnum):
    """Owning teams that can be assigned to an incident."""

    PLATFORM = "platform"
    BACKEND = "backend"
    DATABASE = "database"
    NETWORK = "network"
    SECURITY = "security"
    SRE = "sre"
    UNKNOWN = "unknown"
