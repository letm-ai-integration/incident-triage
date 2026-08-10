from app.agents.base import BaseAgent
from app.domain.models import Classification, Incident
from app.rules.classification import classify_incident
from app.rules.ownership import ownership_for


class ClassificationAgent(BaseAgent[Incident, Classification]):
    """Deterministic classification agent using rule-based heuristics.

    This is a stub that uses the keyword rules; an LLM-backed variant can
    subclass and override :meth:`run`.
    """

    name = "classification"

    async def run(self, incident: Incident) -> Classification:
        category, severity = classify_incident(incident.title, incident.description)
        return Classification(
            category=category,
            severity=severity,
            confidence=0.9,
            rationale=f"rules: category={category}, severity={severity}",
            assigned_team=ownership_for(category),
        )
