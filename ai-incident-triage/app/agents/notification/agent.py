from app.agents.base import BaseAgent
from app.domain.models import IncidentReport


class NotificationAgent(BaseAgent[IncidentReport, str]):
    """Sends the notification for the finalized report.

    Stub implementation returns a confirmation message.
    """

    name = "notification"

    async def run(self, report: IncidentReport) -> str:
        return f"Notified stakeholders about: {report.title}"
