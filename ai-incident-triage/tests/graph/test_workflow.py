"""Integration tests for the triage LangGraph workflow.

Validates real orchestration — compilation, execution over representative
mock incidents, state propagation between nodes, conditional routing, the
reinvestigation loop, and error handling — using deterministic rule-based
fallbacks (no LLM/network dependency).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.enums.incident_type import IncidentType
from app.domain.enums.priority import Priority
from app.domain.enums.status import IncidentStatus, NotificationStatus
from app.graph.router import (
    route_after_approval,
    route_after_classification,
    route_after_verification,
)
from app.graph.workflow import build_triage_graph, compile_triage_graph, triage_graph
from app.services.investigation_service import investigation_service
from app.services.notification_service import notification_service

INCIDENTS = Path(__file__).resolve().parents[2] / "data" / "incidents"
RECURSION_LIMIT = 50


def _deps(**extra) -> dict:
    deps = {
        "auto_approve": True,
        "investigation_service": investigation_service,
        "notification_service": notification_service,
    }
    deps.update(extra)
    return deps


def _run(raw_input: dict, **deps_extra):
    return triage_graph.invoke(
        {"raw_input": raw_input},
        config={"configurable": {"deps": _deps(**deps_extra)}, "recursion_limit": RECURSION_LIMIT},
    )


def _load(name: str) -> dict:
    return json.loads((INCIDENTS / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Graph creation / compilation
# ---------------------------------------------------------------------------


def test_graph_compiles_with_expected_nodes_and_edges():
    graph = compile_triage_graph()
    nodes = set(graph.get_graph().nodes)
    assert {
        "ingestion", "classification", "investigation",
        "investigation_summary", "rca_report", "approval",
        "verification", "notification",
    } <= nodes


def test_build_triage_graph_registers_all_nodes_before_compilation():
    graph = build_triage_graph()
    assert len(graph.nodes) == 8  # builder-tracked node names


# ---------------------------------------------------------------------------
# 2-4. Execution, agent/node execution, state propagation (resolved flow)
# ---------------------------------------------------------------------------


def test_end_to_end_database_timeout_resolves():
    result = _run(_load("database_timeout.json"))

    # ingestion -> classification propagation
    assert result["incident"].title.startswith("Database connection pool exhausted")
    assert result["incident_type"] == IncidentType.DATABASE

    # investigation sub-agents all reported into dedicated state fields
    for field in ("log_analysis", "runbook_analysis", "kubernetes_analysis"):
        assert result[field].source in {"log_analysis", "runbook", "kubernetes"}
    sources = {e.source for e in result["evidence"]}
    assert sources == {"log_analysis", "runbook", "kubernetes"}

    # summary -> rca -> approval -> verification -> notification propagation
    assert result["investigation_summary"]["evidence_count"] >= 3
    assert result["root_cause"].primary_cause.description
    assert result["approval"].approved is True
    assert result["verification_result"].is_resolved is True
    assert result["is_resolved"] is True
    assert result["notification_status"] == NotificationStatus.NOTIFIED
    assert result["incident_report"].incident_id == result["incident_id"]
    assert not result.get("errors")


@pytest.mark.parametrize(
    "sample",
    ["http503.json", "crashloopbackoff.json", "third_party_timeout.json",
     "deployment_regression.json"],
)
def test_all_rich_mock_incidents_flow_end_to_end(sample: str):
    result = _run(_load(sample))
    assert result.get("is_resolved") is True
    assert result.get("notification_status") == NotificationStatus.NOTIFIED
    assert result.get("incident_report") is not None


# ---------------------------------------------------------------------------
# 5. Conditional routing
# ---------------------------------------------------------------------------


def test_route_after_classification_full_investigation_for_p1():
    from app.domain.models.classification import ClassificationResult
    result = ClassificationResult(
        incident_type=IncidentType.DATABASE, priority=Priority.P1,
        confidence=0.9, reasoning="t", affected_services=[], suggested_teams=[],
        agrees_with_rule=True,
    )
    assert route_after_classification({"classification": result}) == "full_investigation"


def test_route_after_classification_auto_resolve_for_p4():
    from app.domain.models.classification import ClassificationResult
    result = ClassificationResult(
        incident_type=IncidentType.APPLICATION, priority=Priority.P4,
        confidence=0.9, reasoning="t", affected_services=[], suggested_teams=[],
        agrees_with_rule=True,
    )
    assert route_after_classification({"classification": result}) == "auto_resolve"


def test_route_after_approval_rejected_on_disapproval():
    from datetime import UTC, datetime

    from app.domain.models.approval import ApprovalDecision
    decision = ApprovalDecision(
        approved=False, reviewer="x", comments="",
        timestamp=datetime.now(UTC),
    )
    assert route_after_approval({"approval": decision}) == "rejected"


def test_route_after_verification_reinvestigates_then_completes():
    from app.domain.models.verification import VerificationResult

    unresolved = VerificationResult(is_resolved=False, needs_reinvestigation=True)
    assert route_after_verification({"verification_result": unresolved, "retry_count": 0}) == "reinvestigate"
    # retries exhausted -> completed even when unresolved
    exhausted = {"verification_result": unresolved, "retry_count": 3}
    assert route_after_verification(exhausted) == "completed"
    resolved = VerificationResult(is_resolved=True, needs_reinvestigation=False)
    assert route_after_verification({"verification_result": resolved}) == "completed"


def test_unresolved_incident_loops_then_terminates_unresolved():
    """Telemetry-gap sample has no corroborating signal -> verification
    fails -> reinvestigation loop bounded by MAX_INVESTIGATION_RETRIES ->
    terminates at notification with an unresolved outcome."""
    result = _run(_load("telemetry-gap.json"))
    assert result["is_resolved"] is False
    assert result["investigation_status"] == IncidentStatus.UNRESOLVED
    assert result["retry_count"] > 0  # loop actually ran
    assert result["notification_status"] == NotificationStatus.NOTIFIED


# ---------------------------------------------------------------------------
# 6. Final output shape
# ---------------------------------------------------------------------------


def test_final_state_contains_report_and_markdown_renderable():
    from app.services.rca_report_service import render_markdown_report

    result = _run(_load("http503.json"))
    report = result["incident_report"]
    markdown = render_markdown_report(report)
    assert report.incident_id in markdown
    assert "Root Cause" in markdown or "root cause" in markdown.lower()


# ---------------------------------------------------------------------------
# 7. Failure / error handling
# ---------------------------------------------------------------------------


def test_agent_failure_is_caught_and_recorded_not_raised():
    def failing_investigation(state, deps):
        raise RuntimeError("mock sub-agent exploded")

    result = triage_graph.invoke(
        {"raw_input": _load("database_timeout.json")},
        config={
            "configurable": {"deps": _deps(investigation_service=failing_investigation)},
            "recursion_limit": RECURSION_LIMIT,
        },
    )
    assert any("investigation failed" in e for e in result.get("errors", []))
    # pipeline still reaches a terminal notification stage
    assert result.get("notification_status") is not None


def test_notification_failure_marks_failed_but_completes():
    def failing_notification(state, deps):
        raise RuntimeError("smtp down")

    result = triage_graph.invoke(
        {"raw_input": _load("database_timeout.json")},
        config={
            "configurable": {"deps": _deps(notification_service=failing_notification)},
            "recursion_limit": RECURSION_LIMIT,
        },
    )
    assert any("notification failed" in e for e in result.get("errors", []))
