from app.agents.base import BaseAgent
from app.domain.models import Evidence, Hypothesis, Incident


class KubernetesAgent(BaseAgent[Incident, tuple[list[Evidence], list[Hypothesis]]]):
    """Analyzes kubernetes events attached to the incident."""

    name = "kubernetes"

    async def run(self, incident: Incident) -> tuple[list[Evidence], list[Hypothesis]]:
        events = incident.raw.get("kubernetes", [])
        if not events:
            return [], []
        evidence = [
            Evidence(source="kubernetes", summary=event, content=event, confidence=0.75)
            for event in events
        ]
        hypotheses = [
            Hypothesis(
                description=f"K8s-based hypothesis: {events[0][:120]}", confidence=0.65
            )
        ]
        return evidence, hypotheses
