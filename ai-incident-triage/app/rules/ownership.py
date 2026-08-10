"""Team ownership rules mapping incident categories to owning teams."""

from app.domain.enums import IncidentType, Team

CATEGORY_OWNER_MAP: dict[IncidentType, Team] = {
    IncidentType.DATABASE: Team.DATABASE,
    IncidentType.INFRASTRUCTURE: Team.PLATFORM,
    IncidentType.NETWORK: Team.NETWORK,
    IncidentType.APPLICATION: Team.BACKEND,
    IncidentType.SECURITY: Team.SECURITY,
    IncidentType.UNKNOWN: Team.UNKNOWN,
}


def ownership_for(category: IncidentType) -> Team:
    return CATEGORY_OWNER_MAP.get(category, Team.UNKNOWN)
