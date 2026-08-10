"""Tests for the AI Incident Triage v2 workflow assembly and execution."""

from __future__ import annotations

import asyncio
from typing import Any

from langgraph.types import Command

from app.domain.models import ApprovalStatus
from app.graph import (
    APPROVAL,
    CLASSIFICATION,
    INGESTION,
    INVESTIGATION,
    INVESTIGATION_SUMMARY,
    NOTIFICATION,
    RCA_REPORT,
    V2_NODES,
    VERIFICATION,
    build_workflow,
    compile_workflow,
    create_checkpointer,
)
from app.graph.router import route_after_verification

EXPECTED_NODES = [
    INGESTION,
    CLASSIFICATION,
    INVESTIGATION,
    INVESTIGATION_SUMMARY,
    RCA_REPORT,
    APPROVAL,
    VERIFICATION,
    NOTIFICATION,
]

EXPECTED_EDGES = [
    ("__start__", INGESTION),
    (INGESTION, CLASSIFICATION),
    (CLASSIFICATION, INVESTIGATION),
    (INVESTIGATION, INVESTIGATION_SUMMARY),
    (INVESTIGATION_SUMMARY, RCA_REPORT),
    (RCA_REPORT, APPROVAL),
    (APPROVAL, VERIFICATION),
    (NOTIFICATION, "__end__"),
]

CONDITIONAL_SOURCE = VERIFICATION
CONDITIONAL_ROUTES = {"notification": NOTIFICATION, "investigation": INVESTIGATION}


def _payload(resolved: bool, **extra: Any) -> dict:
    return {
        "title": "Database connection pool exhausted",
        "description": "Critical outage: connection pool timeout in production",
        "raw": {
            "resolved": resolved,
            "logs": ["ERROR: connection pool timeout", "WARN: retry failed"],
            "kubernetes": ["CrashLoopBackOff pod web-0"],
            "runbooks": ["Runbook: scale connection pool"],
        },
        **extra,
    }


class TestWorkflowStructure:
    def test_all_v2_nodes_registered(self) -> None:
        graph = build_workflow()
        for node in V2_NODES:
            assert node in graph.nodes, f"missing node {node}"

    def test_v2_node_list_matches_expected(self) -> None:
        assert V2_NODES == EXPECTED_NODES

    def test_expected_edges_exist(self) -> None:
        graph = build_workflow()
        for source, target in EXPECTED_EDGES:
            assert (source, target) in graph.edges, f"missing edge {source}->{target}"

    def test_conditional_edge_source(self) -> None:
        graph = build_workflow()
        assert CONDITIONAL_SOURCE in graph.nodes


class TestRouter:
    def test_route_resolved_to_notification(self) -> None:
        route = route_after_verification(
            {"verification": {"resolved": True}}  # type: ignore[typeddict-item]
        )
        assert route == NOTIFICATION

    def test_route_unresolved_to_investigation(self) -> None:
        route = route_after_verification(
            {"verification": {"resolved": False}}  # type: ignore[typeddict-item]
        )
        assert route == INVESTIGATION

    def test_route_unknown_verification_defaults_to_investigation(self) -> None:
        route = route_after_verification({})  # type: ignore[typeddict-item]
        assert route == INVESTIGATION


class TestWorkflowExecution:
    def test_graph_compiles(self) -> None:
        compiled = compile_workflow(checkpointer=create_checkpointer())
        assert compiled is not None

    def test_graph_executes_resolved_flow(self) -> None:
        async def run() -> None:
            checkpointer = create_checkpointer()
            compiled = compile_workflow(checkpointer=checkpointer)
            cfg = {"configurable": {"thread_id": "wf-resolved"}}

            # First pass halts at the approval interrupt.
            result = await compiled.ainvoke({"incident": _payload(resolved=True)}, cfg)
            assert result.get("incident") is not None
            assert result.get("classification") is not None
            assert result.get("investigation_summary") is not None
            assert result.get("rca_report") is not None
            assert "__interrupt__" in result

            # Resume with an approved decision.
            resumed = await compiled.ainvoke(Command(resume={"approved": True}), cfg)
            assert resumed.get("approval") is not None
            assert resumed["approval"].status == ApprovalStatus.APPROVED
            assert resumed.get("verification") is not None
            assert resumed["verification"].resolved is True
            assert resumed.get("notification")
            assert "Notified" in resumed["notification"]

        asyncio.run(run())

    def test_graph_unresolved_loops_back_to_investigation(self) -> None:
        async def run() -> None:
            checkpointer = create_checkpointer()
            compiled = compile_workflow(checkpointer=checkpointer)
            cfg = {"configurable": {"thread_id": "wf-unresolved"}}

            result = await compiled.ainvoke({"incident": _payload(resolved=False)}, cfg)
            assert "__interrupt__" in result

            resumed = await compiled.ainvoke(Command(resume={"approved": True}), cfg)
            # Verification reports unresolved -> router sends back to investigation.
            assert resumed.get("verification") is not None
            assert resumed["verification"].resolved is False
            # The workflow has not reached notification yet; it is looping.
            assert resumed.get("notification") is None

        asyncio.run(run())

    def test_rejected_approval_is_recorded(self) -> None:
        async def run() -> None:
            checkpointer = create_checkpointer()
            compiled = compile_workflow(checkpointer=checkpointer)
            cfg = {"configurable": {"thread_id": "wf-rejected"}}

            result = await compiled.ainvoke({"incident": _payload(resolved=True)}, cfg)
            assert "__interrupt__" in result

            resumed = await compiled.ainvoke(
                Command(resume={"approved": False, "comments": "needs more data"}), cfg
            )
            assert resumed["approval"].status == ApprovalStatus.REJECTED
            assert resumed["approval"].comments == "needs more data"

        asyncio.run(run())
