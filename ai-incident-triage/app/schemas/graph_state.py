"""Graph state contract for the AI Incident Triage v2 workflow.

This is the single authoritative state abstraction used by the graph. It is a
``TypedDict`` so nodes can return partial state updates and LangGraph merges
them via the standard dict reducer.
"""

from typing import TypedDict

from app.domain.models import (
    Approval,
    Classification,
    Incident,
    IncidentReport,
    InvestigationSummary,
    Verification,
)


class IncidentTriageState(TypedDict, total=False):
    """Shared state flowing through the v2 triage graph.

    v2 fields:
    * ``incident`` — normalized incident
    * ``classification`` — category + severity (classification node)
    * ``investigation_summary`` — consolidated findings (investigation_summary node)
    * ``rca_report`` — root cause + confidence + generated report (rca_report node)
    * ``approval`` — human approval decision (approval node)
    * ``verification`` — resolved / unresolved result (verification node)
    * ``notification`` — notification outcome (notification node)
    """

    incident: Incident
    classification: Classification
    investigation_summary: InvestigationSummary
    rca_report: IncidentReport
    approval: Approval
    verification: Verification
    notification: str
