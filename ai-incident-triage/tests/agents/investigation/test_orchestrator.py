"""Tests for the Investigation Orchestrator and its subgraph.

Covers the orchestration architecture end to end:

1. the orchestrator executes,
2. all three sub-agents are invoked through the phase subgraph,
3. results are aggregated into a structured outcome,
4. the shared graph state receives the investigation findings
   (via ``investigation_service``, the default of ``investigation_node``),
5. downstream agents consume that state,
6. a representative mock incident flows through the whole graph,
7. sub-agent failures degrade instead of killing the run.

All tests run on deterministic fallbacks -- no LLM or network required.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.agents.investigation import orchestrator, subgraph
from app.agents.investigation.orchestrator import (
    InvestigationOutcome,
    investigate,
    run_investigation,
)
from app.domain.enums.environment import Environment
from app.domain.enums.status import IncidentStatus, NotificationStatus
from app.domain.models.evidence import Evidence
from app.domain.models.incident import Incident
from app.graph.workflow import triage_graph
from app.services.investigation_service import investigation_service

INCIDENTS = Path(__file__).resolve().parents[3] / "data" / "incidents"
RECURSION_LIMIT = 50


def _incident() -> Incident:
    return Incident(
        incident_id="INC-TEST",
        title="Database connection pool exhausted",
        description="checkouts failing, connection timeout on checkout-db",
        source="test",
        service="checkout-db",
        environment=Environment.PRODUCTION,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        raw_logs=["ConnectionError: connection refused after timeout"],
    )


def _run_graph(raw_input: dict, **deps_extra) -> dict:
    deps = {"auto_approve": True, "notification_service": None}
    from app.services.notification_service import notification_service

    deps = {
        "auto_approve": True,
        # no investigation_service injected: exercises the node's real default
        "notification_service": notification_service,
    }
    deps.update(deps_extra)
    return triage_graph.invoke(
        {"raw_input": raw_input},
        config={"configurable": {"deps": deps}, "recursion_limit": RECURSION_LIMIT},
    )


# ---------------------------------------------------------------------------
# Subgraph structure (what the PNG is generated from)
# ---------------------------------------------------------------------------


def test_phase_subgraph_has_parallel_fanout_structure():
    graph_def = subgraph.investigation_phase_graph.get_graph()
    nodes = set(graph_def.nodes)
    assert {"log_analysis", "kubernetes", "runbook", "synthesize_outcome"} <= nodes
    # all three sub-agents start from START and fan in to synthesize_outcome
    edges = {(e.source, e.target) for e in graph_def.edges}
    for name in ("log_analysis", "kubernetes", "runbook"):
        assert ("__start__", name) in edges
        assert (name, "synthesize_outcome") in edges


# ---------------------------------------------------------------------------
# Test 1 + 2 + 3: orchestrator executes, subagents invoked, results aggregated
# ---------------------------------------------------------------------------


def test_orchestrator_invokes_all_three_subagents(monkeypatch):
    calls = []

    async def fake_log(incident, llm, classification=None):
        calls.append("log_analysis")
        return Evidence(evidence_id="ev-log-1", source="log_analysis",
                        finding="error signals found", severity="high", raw_data={})

    async def fake_k8s(incident, classification, llm):
        calls.append("kubernetes")
        return Evidence(evidence_id="ev-k8s-1", source="kubernetes",
                        finding="degraded pods", severity="medium", raw_data={})

    def fake_runbook(alert_data, classification=None):
        calls.append("runbook")
        return Evidence(evidence_id="ev-rb-1", source="runbook",
                        finding="matched runbook", severity="medium", raw_data={}), None

    monkeypatch.setattr(subgraph, "_log_evidence", fake_log)
    monkeypatch.setattr(subgraph, "_kubernetes_evidence", fake_k8s)
    monkeypatch.setattr(subgraph, "_runbook_evidence", fake_runbook)

    outcome = asyncio.run(run_investigation(_incident()))

    assert sorted(calls) == ["kubernetes", "log_analysis", "runbook"]
    assert isinstance(outcome, InvestigationOutcome)


def test_orchestrator_aggregates_subagent_results_into_outcome():
    outcome = investigate(_incident())

    sources = {e.source for e in outcome.evidence}
    assert sources == {"log_analysis", "kubernetes", "runbook"}
    assert outcome.log_analysis is outcome.evidence[0]
    assert outcome.runbook_analysis is outcome.evidence[1]
    assert outcome.kubernetes_analysis is outcome.evidence[2]
    assert outcome.hypotheses, "at least one hypothesis synthesized"
    assert 0.0 < outcome.confidence <= 0.95
    top = max(outcome.hypotheses, key=lambda h: h.confidence)
    assert top.confidence == pytest.approx(outcome.confidence)


# ---------------------------------------------------------------------------
# Test 4: shared state updated by the service/node layer
# ---------------------------------------------------------------------------


def test_investigation_service_writes_findings_to_shared_state_shape():
    update = investigation_service({"incident": _incident()}, {})

    for key in ("evidence", "hypotheses", "log_analysis",
                "runbook_analysis", "kubernetes_analysis"):
        assert update.get(key), f"missing shared-state key {key}"
    assert {e.source for e in update["evidence"]} == {
        "log_analysis", "kubernetes", "runbook"
    }
    assert update["investigation_status"] == IncidentStatus.INVESTIGATING


# ---------------------------------------------------------------------------
# Test 5: downstream agents consume the investigation state
# ---------------------------------------------------------------------------


def test_downstream_rca_consumes_orchestrated_evidence():
    raw = (INCIDENTS / "database_timeout.json").read_text(encoding="utf-8")
    import json

    result = _run_graph(json.loads(raw))

    orchestrated_ids = {e.evidence_id for e in result["evidence"]}
    report_evidence_ids = {e.evidence_id for e in result["incident_report"].evidence.items}
    assert orchestrated_ids == report_evidence_ids
    # RCA primary cause is derived from the orchestrator's hypotheses, not invented
    assert result["root_cause"].primary_cause.description
    summary_sources = set(result["investigation_summary"]["sources"])
    assert summary_sources == {"log_analysis", "kubernetes", "runbook"}


# ---------------------------------------------------------------------------
# Test 6: end-to-end flow through the parent graph (default service path)
# ---------------------------------------------------------------------------


def test_end_to_end_via_default_orchestrator_node():
    import json

    result = _run_graph(json.loads((INCIDENTS / "database_timeout.json").read_text(encoding="utf-8")))

    assert {e.source for e in result["evidence"]} == {
        "log_analysis", "kubernetes", "runbook"
    }
    assert result["investigation_summary"]["evidence_count"] >= 3
    assert result["is_resolved"] is True
    assert result["notification_status"] == NotificationStatus.NOTIFIED
    assert not result.get("errors")


# ---------------------------------------------------------------------------
# Test 7: sub-agent failure handling (orchestrator degrades, never raises)
# ---------------------------------------------------------------------------


def test_failing_subagent_dependency_degrades_to_info_evidence(monkeypatch):
    """A broken sub-agent dependency (mock k8s tool / log keyword scan) must
    degrade to an ``info`` Evidence item, not kill the investigation."""

    async def exploding_tool(self, **kwargs):
        raise RuntimeError("k8s api down")

    monkeypatch.setattr(orchestrator.MockKubernetesTool, "run", exploding_tool)

    outcome = investigate(_incident())

    k8s_ev = outcome.kubernetes_analysis
    assert k8s_ev.severity == "info"
    assert "failed" in k8s_ev.finding.lower()
    assert "k8s api down" in k8s_ev.raw_data["error"]
    # the other two subagents still contributed
    assert {e.source for e in outcome.evidence} >= {"log_analysis", "runbook"}


def test_failing_log_analysis_degrades_to_info_evidence(monkeypatch):
    def exploding_signals(texts):
        raise RuntimeError("log backend down")

    monkeypatch.setattr(orchestrator, "_keyword_signals", exploding_signals)

    outcome = investigate(_incident())

    log_ev = outcome.log_analysis
    assert log_ev.severity == "info"
    assert "failed" in log_ev.finding.lower()
    assert "log backend down" in log_ev.raw_data["error"]
    assert {e.source for e in outcome.evidence} >= {"kubernetes", "runbook"}
