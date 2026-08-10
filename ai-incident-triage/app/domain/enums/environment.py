from enum import StrEnum


class Environment(StrEnum):
    """Deployment environment an incident belongs to."""

    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    TEST = "test"
