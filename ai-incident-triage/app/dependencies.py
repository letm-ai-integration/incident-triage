"""Dependency container for graph nodes.

Nodes should never construct application-wide clients on every execution.
Instead they receive shared agent/service instances from this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.classification import ClassificationAgent
from app.agents.investigation import InvestigationOrchestrator
from app.agents.notification import NotificationAgent
from app.agents.rca_report import RcaReportAgent
from app.services.approval_service import ApprovalService
from app.services.ingestion_service import IngestionService
from app.services.verification_service import VerificationService


@dataclass
class Dependencies:
    """Shared application dependencies injected into graph nodes."""

    ingestion_service: IngestionService = field(default_factory=IngestionService)
    classification_agent: ClassificationAgent = field(
        default_factory=ClassificationAgent
    )
    investigation_orchestrator: InvestigationOrchestrator = field(
        default_factory=InvestigationOrchestrator
    )
    rca_report_agent: RcaReportAgent = field(default_factory=RcaReportAgent)
    approval_service: ApprovalService = field(default_factory=ApprovalService)
    verification_service: VerificationService = field(
        default_factory=VerificationService
    )
    notification_agent: NotificationAgent = field(default_factory=NotificationAgent)


_default_dependencies: Dependencies | None = None


def get_dependencies() -> Dependencies:
    """Return the process-wide shared dependency container."""
    global _default_dependencies
    if _default_dependencies is None:
        _default_dependencies = Dependencies()
    return _default_dependencies


def reset_dependencies() -> None:
    """Reset the shared dependency container (mainly for tests)."""
    global _default_dependencies
    _default_dependencies = None
