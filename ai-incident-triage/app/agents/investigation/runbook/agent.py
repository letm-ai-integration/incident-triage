from app.agents.base import BaseAgent
from app.domain.models import Evidence, Hypothesis, Incident


class RunbookAgent(BaseAgent[Incident, tuple[list[Evidence], list[Hypothesis]]]):
    """Looks up runbook knowledge for the incident category."""

    name = "runbook"

    async def run(self, incident: Incident) -> tuple[list[Evidence], list[Hypothesis]]:
        runbooks = incident.raw.get("runbooks", [])
        if not runbooks:
            return [], []
        evidence = [
            Evidence(source="runbook", summary=entry, content=entry, confidence=0.6)
            for entry in runbooks
        ]
        return evidence, []
