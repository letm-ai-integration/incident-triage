# LangGraph workflow assembly.
#
# v2 flow:
#   ingestion -> classification (category + severity)
#     -> investigation (parallel sub-agents)
#     -> investigation_summary -> rca_report -> approval
#     -> verification (resolved -> notification; unresolved -> loop to investigation)
#     -> notification
#
# The classification/approval/verification stages branch through the pure
# routing functions in router.py. All node/edge registration goes through
# builder.py's public API.
from app.graph.builder import (
    START,
    END,
    add_conditional_edge,
    add_edge,
    add_node,
    compile_graph,
    create_graph,
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
from app.graph.router import (
    route_after_approval,
    route_after_classification,
    route_after_verification,
)
from app.graph.state import IncidentState


def build_triage_graph():
    """Assemble (but do not compile) the production incident-triage graph."""
    graph = create_graph(state_schema=IncidentState)

    add_node(graph, "ingestion", ingestion_node)
    add_node(graph, "classification", classification_node)
    add_node(graph, "investigation", investigation_node)
    add_node(graph, "investigation_summary", investigation_summary_node)
    add_node(graph, "rca_report", rca_report_node)
    add_node(graph, "approval", approval_node)
    add_node(graph, "verification", verification_node)
    add_node(graph, "notification", notification_node)

    add_edge(graph, START, "ingestion")
    add_edge(graph, "ingestion", "classification")

    add_conditional_edge(
        graph,
        "classification",
        route_after_classification,
        {
            "full_investigation": "investigation",
            "auto_resolve": "notification",
        },
    )

    add_edge(graph, "investigation", "investigation_summary")
    add_edge(graph, "investigation_summary", "rca_report")
    add_edge(graph, "rca_report", "approval")

    add_conditional_edge(
        graph,
        "approval",
        route_after_approval,
        {
            "approved": "verification",
            "rejected": "notification",
        },
    )

    add_conditional_edge(
        graph,
        "verification",
        route_after_verification,
        {
            "reinvestigate": "investigation",
            "completed": "notification",
        },
    )

    add_edge(graph, "notification", END)
    return graph


def compile_triage_graph():
    """Compile the production triage graph into an executable graph."""
    return compile_graph(build_triage_graph())


triage_graph = compile_triage_graph()
