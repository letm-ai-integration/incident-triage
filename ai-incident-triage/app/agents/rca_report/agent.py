from app.agents.base import BaseAgent
from app.domain.models import (
    Incident,
    IncidentReport,
    InvestigationSummary,
    RootCause,
)


class RcaReportAgent(BaseAgent[tuple[Incident, InvestigationSummary], IncidentReport]):
    """Determines root cause + confidence and generates the incident report."""

    name = "rca_report"

    async def run(
        self, incident: Incident, investigation_summary: InvestigationSummary
    ) -> IncidentReport:
        hypotheses = investigation_summary.hypotheses
        best = max(hypotheses, key=lambda h: h.confidence) if hypotheses else None
        root_cause = RootCause(
            root_cause=best.description if best else "No root cause identified",
            confidence=best.confidence if best else 0.0,
            supporting_hypothesis=best,
        )
        return IncidentReport(
            title=f"RCA report: {incident.title}",
            summary=investigation_summary.summary,
            incident=incident,
            root_cause=root_cause,
        )
