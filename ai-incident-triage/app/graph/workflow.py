"""AI Incident Triage v2 workflow assembly.

This module is *application-specific*: it assembles the triage nodes into a
graph using the generic builder API from :mod:`app.graph.builder`.

v2 flow::

    ingestion -> classification -> investigation -> investigation_summary
    -> rca_report -> approval -> verification -> notification

Verification routes resolved incidents to notification and unresolved ones back
to investigation (re-investigation loop).
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from app.domain.models import (
    Approval,
    Classification,
    Evidence,
    Hypothesis,
    Incident,
    IncidentReport,
    InvestigationSummary,
    RootCause,
    Verification,
)
from app.graph.builder import (
    END,
    START,
    GraphContext,
    addConditionalEdge,
    addEdge,
    addNode,
    compileGraph,
    createGraph,
)
from app.graph.nodes import (
    approval_node,
    classification_node,
    ingestion_node,
    investigation_node,
    investigation_summary_node,
    notification_node,
    rca_report_node,
    verification_node,
)
from app.graph.router import route_after_verification
from app.schemas.graph_state import IncidentTriageState

WORKFLOW_NAME = "incident_triage_v2"

# Node name constants shared by the workflow and its tests.
INGESTION = "ingestion"
CLASSIFICATION = "classification"
INVESTIGATION = "investigation"
INVESTIGATION_SUMMARY = "investigation_summary"
RCA_REPORT = "rca_report"
APPROVAL = "approval"
VERIFICATION = "verification"
NOTIFICATION = "notification"

V2_NODES = [
    INGESTION,
    CLASSIFICATION,
    INVESTIGATION,
    INVESTIGATION_SUMMARY,
    RCA_REPORT,
    APPROVAL,
    VERIFICATION,
    NOTIFICATION,
]

# Pydantic models + enums stored in graph state, registered with the checkpoint
# serde so checkpoints deserialize cleanly across versions.
_STATE_MODEL_MODULES: tuple[str, ...] = (
    f"{Incident.__module__}.{Incident.__name__}",
    f"{Classification.__module__}.{Classification.__name__}",
    f"{InvestigationSummary.__module__}.{InvestigationSummary.__name__}",
    f"{IncidentReport.__module__}.{IncidentReport.__name__}",
    f"{Approval.__module__}.{Approval.__name__}",
    f"{Verification.__module__}.{Verification.__name__}",
    f"{Evidence.__module__}.{Evidence.__name__}",
    f"{Hypothesis.__module__}.{Hypothesis.__name__}",
    f"{RootCause.__module__}.{RootCause.__name__}",
    "app.domain.enums.environment.Environment",
    "app.domain.enums.incident_type.IncidentType",
    "app.domain.enums.priority.Priority",
    "app.domain.enums.status.Status",
    "app.domain.enums.team.Team",
)


def create_checkpointer() -> InMemorySaver:
    """Return an in-memory checkpointer with the app's state models registered.

    Use this for local execution and tests. Production deployments should pass
    a durable checkpointer to :func:`compile_workflow` instead.
    """
    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[
            (module.rsplit(".", 1)[0], module.rsplit(".", 1)[1])
            for module in _STATE_MODEL_MODULES
        ]
    )
    return InMemorySaver(serde=serde)


def build_workflow(
    *,
    checkpointer: Any | None = None,
    config: dict[str, Any] | None = None,
) -> GraphContext[IncidentTriageState]:
    """Assemble the v2 triage graph using the generic builder.

    Returns an uncompiled :class:`GraphContext`; call :func:`compile_workflow`
    or :func:`compileGraph` to obtain a runnable graph.
    """
    graph = createGraph(
        IncidentTriageState,
        name=WORKFLOW_NAME,
        checkpointer=checkpointer,
        config=config,
    )

    addNode(graph, INGESTION, ingestion_node)
    addNode(graph, CLASSIFICATION, classification_node)
    addNode(graph, INVESTIGATION, investigation_node)
    addNode(graph, INVESTIGATION_SUMMARY, investigation_summary_node)
    addNode(graph, RCA_REPORT, rca_report_node)
    addNode(graph, APPROVAL, approval_node)
    addNode(graph, VERIFICATION, verification_node)
    addNode(graph, NOTIFICATION, notification_node)

    addEdge(graph, START, INGESTION)
    addEdge(graph, INGESTION, CLASSIFICATION)
    addEdge(graph, CLASSIFICATION, INVESTIGATION)
    addEdge(graph, INVESTIGATION, INVESTIGATION_SUMMARY)
    addEdge(graph, INVESTIGATION_SUMMARY, RCA_REPORT)
    addEdge(graph, RCA_REPORT, APPROVAL)
    addEdge(graph, APPROVAL, VERIFICATION)

    addConditionalEdge(
        graph,
        VERIFICATION,
        route_after_verification,
        path_map={
            "notification": NOTIFICATION,
            "investigation": INVESTIGATION,
        },
    )
    addEdge(graph, NOTIFICATION, END)

    return graph


def compile_workflow(
    *,
    checkpointer: Any | None = None,
    config: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Build and compile the v2 triage graph.

    If ``checkpointer`` is omitted, an in-memory checkpointer configured with
    the app's state models is used (enables interrupt/resume out of the box).
    """
    if checkpointer is None:
        checkpointer = create_checkpointer()
    context = build_workflow(checkpointer=checkpointer, config=config)
    return compileGraph(context, **kwargs)
