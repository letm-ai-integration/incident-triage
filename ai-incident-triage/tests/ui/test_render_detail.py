"""Regression tests for the Active Node Detail panel (app/ui/render_detail.py)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.graph.events import NodeEvent
from app.ui.render_detail import render_detail, render_detail_panel


def _event(**overrides) -> NodeEvent:
    base: dict = {
        "run_id": "run-1",
        "node_name": "classification",
        "status": "running",
        "started_at": None,
        "ended_at": None,
        "duration_ms": None,
    }
    base.update(overrides)
    return NodeEvent(**base)


def test_none_event_renders_waiting_bar_without_disclosure():
    out = render_detail_panel(None)
    assert "Waiting for the first node" in out
    assert "<details" not in out  # nothing to disclose -> no disclosure at all


def test_running_node_without_data_collapsed_by_default_with_empty_state():
    out = render_detail_panel(_event())
    assert not out.startswith("<details open")  # always collapsed by default
    assert "No detailed logs available for this node yet" in out


def test_running_node_with_data_also_collapsed_by_default():
    out = render_detail_panel(
        _event(status="running", input_snapshot={"incident": "INC-1"})
    )
    assert not out.startswith("<details open")
    assert "Input state slice" in out  # content there, just hidden until expanded


def test_completed_node_with_data_collapsed_by_default_with_all_sections():
    out = render_detail_panel(
        _event(
            status="success",
            duration_ms=1500.0,
            input_snapshot={"incident": "INC-1"},
            output_snapshot={"root_cause": "pool exhaustion"},
            agent_trace=[
                {"type": "llm_call", "name": "RCA", "status": "success",
                 "duration_ms": 500.0}
            ],
        )
    )
    assert out.startswith("<details ")
    assert " open" not in out.split(">")[0]  # collapsed by default
    assert "Input state slice" in out
    assert "Output state slice" in out
    assert "Agent trace" in out


def test_naive_started_at_in_live_trace_entry_does_not_crash():
    """Regression: naive tz in a live trace entry used to raise TypeError."""
    event = _event(
        status="running",
        agent_trace=[
            {"type": "subagent", "name": "x", "started_at": "2026-09-11T06:00:00"}
        ],
    )
    out = render_detail(event)
    assert "(so far)" in out  # elapsed-so-far rendered, no crash


def test_malformed_trace_entries_are_skipped_not_fatal():
    event = _event(
        status="success",
        duration_ms=1.0,
        agent_trace=["not-a-dict", None, {"type": "llm_call", "name": "ok"}],
    )
    out = render_detail(event)
    assert "LLM call" in out  # the valid entry rendered, malformed ones skipped


def test_error_event_renders_error_section():
    out = render_detail_panel(_event(status="error", error="kaboom"))
    assert "kaboom" in out


def test_utc_aware_started_at_also_renders_so_far():
    event = _event(
        status="running",
        agent_trace=[
            {"type": "tool_call", "name": "y",
             "started_at": datetime.now(UTC).isoformat()}
        ],
    )
    out = render_detail(event)
    assert "(so far)" in out
