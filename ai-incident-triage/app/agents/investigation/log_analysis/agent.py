from app.agents.base import BaseAgent
from app.domain.models import Evidence, Hypothesis, Incident


class LogAnalysisAgent(BaseAgent[Incident, tuple[list[Evidence], list[Hypothesis]]]):
    """Analyzes log data attached to the incident and produces evidence."""

    name = "log_analysis"

    async def run(self, incident: Incident) -> tuple[list[Evidence], list[Hypothesis]]:
        logs = incident.raw.get("logs", [])
        if not logs:
            return [], []
        evidence = [
            Evidence(source="logs", summary=line, content=line, confidence=0.8)
            for line in logs
        ]
        hypotheses = [
            Hypothesis(
                description=f"Log-based hypothesis: {logs[0][:120]}", confidence=0.7
            )
        ]
        return evidence, hypotheses
