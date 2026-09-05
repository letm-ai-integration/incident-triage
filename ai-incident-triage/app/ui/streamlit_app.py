"""Streamlit UI for the incident-triage LangGraph pipeline.

Run with:

    uv run streamlit run app/ui/streamlit_app.py

This is a local/internal POC tool -- Streamlit has no built-in authentication,
so this should not be exposed on a public network interface without adding an
auth layer in front of it first.

The UI only assembles a ``raw_input`` dict and calls
``app.graph.workflow.triage_graph`` -- it contains no triage logic of its own.
LLM-backed classification/RCA agents are opt-in via the sidebar and are wired
through ``deps`` exactly as any other caller of the graph would, so this file
never needs to duplicate graph/service logic.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import streamlit as st

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("streamlit_app")

from uuid import uuid4

from app.config import get_settings
from app.domain.enums.environment import Environment
from app.domain.enums.priority import Priority
from app.domain.models.report import IncidentReport
from app.graph.events import NodeEvent
from app.graph.introspect import get_graph_topology
from app.graph.workflow import stream_triage_graph, triage_graph
from app.services.classification_service import classification_service
from app.services.investigation_service import investigation_service
from app.services.notification_service import notification_service
from app.services.rca_report_service import rca_report_service, render_markdown_report
from app.ui import theme
from app.ui.render_detail import render_detail
from app.ui.render_graph import canvas_height, render_graph
from app.ui.render_timeline import render_timeline

SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "incidents"


def _load_samples() -> dict[str, dict[str, Any]]:
    samples: dict[str, dict[str, Any]] = {}
    if not SAMPLES_DIR.is_dir():
        return samples
    for path in sorted(SAMPLES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data:  # skip empty/placeholder {} files
            samples[path.stem] = data
    return samples


def _llm_configured() -> bool:
    return bool(get_settings().active_llm_config().get("api_key"))


def _build_raw_input_from_form() -> dict[str, Any]:
    form_state = st.session_state.get("form", {})
    tags = [t.strip() for t in form_state.get("tags", "").split(",") if t.strip()]
    logs = [line for line in form_state.get("logs", "").splitlines() if line.strip()]
    raw: dict[str, Any] = {
        "title": form_state.get("title", ""),
        "description": form_state.get("description", ""),
        "source": form_state.get("source", "manual-ui"),
        "service": form_state.get("service", ""),
        "environment": form_state.get("environment", Environment.PRODUCTION.value),
        "tags": tags,
        "timestamp": form_state.get("timestamp", datetime.now(UTC)).isoformat(),
        "logs": logs,
    }
    priority_hint = form_state.get("priority_hint")
    if priority_hint and priority_hint != "auto-detect":
        raw["priority_hint"] = priority_hint
    for key, field in (("events", "events_json"), ("alerts", "alerts_json"), ("metrics", "metrics_json"), ("metadata", "metadata_json")):
        text = form_state.get(field, "").strip()
        if text:
            raw[key] = json.loads(text)  # validated on submit before this is called
    return raw


def _validate_advanced_json(form_state: dict[str, Any]) -> str | None:
    """Return an error message if any advanced JSON field is malformed, else None."""
    for label, field in (("Events", "events_json"), ("Alerts", "alerts_json"), ("Metrics", "metrics_json"), ("Metadata", "metadata_json")):
        text = form_state.get(field, "").strip()
        if not text:
            continue
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            return f"{label} field is not valid JSON: {exc}"
    return None


def _render_sidebar() -> dict[str, Any]:
    st.sidebar.header("Run options")
    auto_approve = st.sidebar.checkbox("Auto-approve", value=True, help="Skip human sign-off for P1/P2 or low-confidence incidents.")

    llm_available = _llm_configured()
    if not llm_available:
        st.sidebar.info("No LLM API key configured -- running on deterministic rule-based fallbacks.")
    use_llm = st.sidebar.checkbox(
        "Use LLM-backed agents",
        value=llm_available,
        disabled=not llm_available,
        help=(
            "Classification, investigation (log analysis + Kubernetes sub-agents, plus the "
            "runbook RAG lookup), and root-cause analysis use the real agents instead of "
            "rule-based fallbacks."
        ),
    )

    deps: dict[str, Any] = {
        "auto_approve": auto_approve,
        # Investigation/notification services work without an LLM key (they
        # fall back to deterministic sub-agent analysis internally), so they
        # are wired unconditionally -- same as the CLI entry point.
        "investigation_service": investigation_service,
        "notification_service": notification_service,
    }
    if use_llm and llm_available:
        deps["use_llm"] = True
        deps["classification_service"] = classification_service
        deps["investigation_service"] = investigation_service
        deps["rca_report_service"] = rca_report_service

    st.sidebar.caption(f"LLM provider configured: {'yes' if llm_available else 'no'}")

    # Status legend (Problem 4): a small, static colour -> meaning map so the
    # node/pill colours on the canvas and timeline are self-explanatory.
    st.sidebar.markdown('<div class="it-zone-title">Status legend</div>', unsafe_allow_html=True)
    st.sidebar.markdown(theme.legend_html(), unsafe_allow_html=True)
    return deps


def _render_form_tab(samples: dict[str, dict[str, Any]]) -> None:
    st.session_state.setdefault("form", {})
    sample_name = st.selectbox("Load sample incident", ["(none)"] + list(samples.keys()), key="form_sample")
    if st.button("Load into form", key="load_form_sample") and sample_name != "(none)":
        sample = samples[sample_name]
        st.session_state["form"] = {
            "title": sample.get("title", ""),
            "description": sample.get("description", ""),
            "source": sample.get("source", "manual-ui"),
            "service": sample.get("service", ""),
            "environment": sample.get("environment", Environment.PRODUCTION.value),
            "priority_hint": sample.get("priority_hint", "auto-detect"),
            "tags": ", ".join(sample.get("tags", [])),
            "timestamp": datetime.now(UTC),
            "logs": "\n".join(sample.get("logs", [])),
            "events_json": json.dumps(sample.get("events", []), indent=2) if sample.get("events") else "",
            "alerts_json": json.dumps(sample.get("alerts", []), indent=2) if sample.get("alerts") else "",
            "metrics_json": json.dumps(sample.get("metrics", {}), indent=2) if sample.get("metrics") else "",
            "metadata_json": json.dumps(sample.get("metadata", {}), indent=2) if sample.get("metadata") else "",
        }
        st.rerun()

    form_state = st.session_state["form"]
    col1, col2 = st.columns(2)
    with col1:
        form_state["title"] = st.text_input("Title", value=form_state.get("title", ""))
        form_state["service"] = st.text_input("Service", value=form_state.get("service", ""))
        form_state["source"] = st.text_input("Source", value=form_state.get("source", "manual-ui"))
        form_state["tags"] = st.text_input("Tags (comma-separated)", value=form_state.get("tags", ""))
    with col2:
        form_state["environment"] = st.selectbox(
            "Environment", [e.value for e in Environment],
            index=[e.value for e in Environment].index(form_state.get("environment", Environment.PRODUCTION.value)),
        )
        priority_options = ["auto-detect"] + [p.value for p in Priority]
        current_priority = form_state.get("priority_hint") or "auto-detect"
        form_state["priority_hint"] = st.selectbox(
            "Priority hint", priority_options,
            index=priority_options.index(current_priority) if current_priority in priority_options else 0,
        )
        form_state["timestamp"] = datetime.now(UTC)

    form_state["description"] = st.text_area("Description", value=form_state.get("description", ""), height=100)
    form_state["logs"] = st.text_area("Log lines (one per line)", value=form_state.get("logs", ""), height=150)

    with st.expander("Advanced: events / alerts / metrics / metadata (raw JSON, optional)"):
        form_state["events_json"] = st.text_area("Events (JSON list)", value=form_state.get("events_json", ""), height=80)
        form_state["alerts_json"] = st.text_area("Alerts (JSON list)", value=form_state.get("alerts_json", ""), height=80)
        form_state["metrics_json"] = st.text_area("Metrics (JSON object)", value=form_state.get("metrics_json", ""), height=80)
        form_state["metadata_json"] = st.text_area("Metadata (JSON object)", value=form_state.get("metadata_json", ""), height=80)

    if st.button("Run Triage", type="primary", key="run_form"):
        error = _validate_advanced_json(form_state)
        if error:
            st.error(error)
        elif not form_state.get("title") or not form_state.get("service"):
            st.error("Title and Service are required.")
        else:
            _start_run(_build_raw_input_from_form())


_JSON_TEMPLATE = json.dumps(
    {"title": "", "description": "", "source": "manual-ui", "service": "", "environment": "PRODUCTION", "tags": [], "logs": []},
    indent=2,
)


def _render_json_tab(samples: dict[str, dict[str, Any]]) -> None:
    st.session_state.setdefault("json_text", _JSON_TEMPLATE)
    sample_name = st.selectbox("Load sample incident", ["(none)"] + list(samples.keys()), key="json_sample")
    if st.button("Load into JSON box", key="load_json_sample") and sample_name != "(none)":
        st.session_state["json_text"] = json.dumps(samples[sample_name], indent=2)
        st.rerun()

    uploaded = st.file_uploader("Or upload an incident JSON file", type=["json"])
    text = st.text_area("Incident JSON", height=350, key="json_text")

    if st.button("Run Triage", type="primary", key="run_json"):
        raw_text = text
        if uploaded is not None:
            try:
                raw_text = uploaded.getvalue().decode("utf-8")
            except UnicodeDecodeError:
                st.error("Uploaded file is not valid UTF-8 text.")
                return
        try:
            raw_input = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
            return
        if not isinstance(raw_input, dict) or not raw_input.get("title") or not raw_input.get("service"):
            st.error("Incident JSON must be an object with at least 'title' and 'service'.")
            return
        _start_run(raw_input)


def _start_run(raw_input: dict[str, Any]) -> None:
    """Queue a run and step the app so it streams live on the next rerun."""
    st.session_state["_pending_input"] = raw_input
    st.session_state["_run_requested"] = True
    st.rerun()


def _merged_event(events: list[NodeEvent], node_name: str) -> NodeEvent | None:
    """Fuse a node's ``running`` (input) and terminal (output/trace) events."""
    running: NodeEvent | None = None
    terminal: NodeEvent | None = None
    for ev in events:
        if ev.node_name != node_name:
            continue
        if ev.status == "running":
            running = ev
        elif ev.status in ("success", "error"):
            terminal = ev
    base = terminal or running
    if base is None:
        return None
    return NodeEvent(
        run_id=base.run_id,
        node_name=node_name,
        status=base.status,
        started_at=terminal.started_at if terminal else running.started_at,
        ended_at=terminal.ended_at if terminal else running.ended_at,
        duration_ms=terminal.duration_ms if terminal else running.duration_ms,
        input_snapshot=running.input_snapshot if running else terminal.input_snapshot,
        output_snapshot=terminal.output_snapshot if terminal else None,
        agent_trace=terminal.agent_trace if terminal else (running.agent_trace or []),
        error=terminal.error if terminal else running.error,
    )


def _panel_height(topology: dict[str, Any]) -> int:
    """Fixed pixel height shared by the graph/timeline and detail containers.

    Both side-by-side zones are locked to the same height (the graph canvas's
    intrinsic height plus padding) and scroll internally, so a long run can
    never stretch the page -- long detail content scrolls inside its panel.
    """
    return int(canvas_height(topology)) + 24


def _render_live_zones(
    topology: dict[str, Any],
    bus: Any,
    last_node: str | None,
    graph_slot: Any,
    timeline_slot: Any,
    detail_slot: Any,
) -> None:
    """Re-render the three live zones from the current state of the bus.

    Called on *every* streamed event -- including ``running`` and sub-agent
    status signals -- so in-progress work is visible the moment it starts.

    The detail panel auto-follows ``last_node``; the caller updates that pointer
    *before* calling this, so the panel always reflects the freshest event, never
    the previous one.
    """
    graph_slot.markdown(
        render_graph(
            topology,
            bus.node_states,
            bus.subagent_states,
            run_progress={"started": bool(bus.events), "completed": bus.completed},
        ),
        unsafe_allow_html=True,
    )
    timeline_slot.markdown(render_timeline(bus.events, bus.node_order()), unsafe_allow_html=True)
    if last_node is None:
        detail_slot.markdown(
            '<span class="it-muted">Waiting for the first node…</span>', unsafe_allow_html=True
        )
        return
    event = bus.merged_event(last_node)
    if event is not None and event.status == "running":
        # The running event's agent_trace was snapshotted at node start; splice
        # in the handler's live entries so sub-agent calls appear (with their
        # own running/success status) while the node is still executing.
        handler = getattr(bus, "trace_handler", None)
        live = handler.live_trace() if handler is not None else []
        if live:
            event.agent_trace = live
    detail_slot.markdown(
        render_detail(event) if event else '<span class="it-muted">No node selected.</span>',
        unsafe_allow_html=True,
    )


def _execute_run(raw_input: dict[str, Any], deps: dict[str, Any]) -> None:
    """Run the graph using the streaming path and render live per-node updates.

    Pattern A: the graph is streamed *within this script execution* and each
    emitted ``NodeEvent`` re-renders the graph canvas, execution timeline and
    detail panel in place -- no ``st.rerun()`` is needed between events.
    """
    run_id = str(uuid4())
    st.markdown("## Live execution")
    topology = get_graph_topology(triage_graph)
    panel_h = _panel_height(topology)
    col_main, col_detail = st.columns([3, 1.4])
    with col_main:
        st.markdown('<div class="it-zone-title">Graph canvas</div>', unsafe_allow_html=True)
        # Fixed-height, internally-scrollable zone (graph canvas + timeline) so
        # the page stays compact regardless of how long the run gets.
        with st.container(height=panel_h, border=True):
            graph_slot = st.empty()
            st.markdown('<div class="it-zone-title">Execution timeline</div>', unsafe_allow_html=True)
            timeline_slot = st.empty()
    with col_detail:
        st.markdown('<div class="it-zone-title">Active node &middot; detail</div>', unsafe_allow_html=True)
        # Same fixed height as the graph zone; long content scrolls inside.
        with st.container(height=panel_h, border=True):
            detail_slot = st.empty()

    final_slot = st.container()
    last_node: str | None = None
    generator, bus = stream_triage_graph(raw_input, deps, run_id=run_id)
    with st.spinner("Running triage pipeline..."):
        # Paint the all-pending canvas + detail placeholder before the first
        # event arrives.
        _render_live_zones(topology, bus, None, graph_slot, timeline_slot, detail_slot)
        try:
            for event in generator:
                if isinstance(event, dict):
                    # Sub-agent live status signal from the custom stream. The
                    # bus is already updated; just follow the parent node it
                    # belongs to (dicts have no .node_name attribute).
                    last_node = event.get("parent") or last_node
                else:
                    # Update the auto-follow pointer BEFORE rendering so the
                    # detail panel never lags one event behind.
                    last_node = event.node_name
                _render_live_zones(topology, bus, last_node, graph_slot, timeline_slot, detail_slot)
            # Final paint: flips END to Completed and completes the timeline.
            _render_live_zones(topology, bus, last_node, graph_slot, timeline_slot, detail_slot)
        except Exception as exc:
            logger.exception("[streamlit] triage stream failed")
            _render_live_zones(topology, bus, last_node, graph_slot, timeline_slot, detail_slot)
            st.error(f"Triage failed: {exc}")

    active = {
        "run_id": run_id,
        "events": bus.events,
        "node_states": bus.node_states,
        "subagent_states": bus.subagent_states,
        "node_order": bus.node_order(),
        "final_state": bus.final_state,
        "deps": deps,
        "completed": bus.completed,
        "error": bus.error,
    }
    st.session_state["active_run"] = active
    st.session_state.setdefault("_run_data", {})[run_id] = active

    title = ""
    if bus.final_state and bus.final_state.get("incident"):
        title = bus.final_state["incident"].title
    runs = st.session_state.setdefault("runs", [])
    runs.insert(
        0,
        {
            "run_id": run_id,
            "title": title,
            "completed": bus.completed,
            "error": bus.error,
            "node_count": len(bus.node_order()),
        },
    )
    st.session_state["runs"] = runs[:20]

    with final_slot:
        if bus.final_state:
            _render_final_result(bus.final_state)
        elif bus.error:
            st.error(f"Triage failed: {bus.error}")


def _render_final_result(result: dict[str, Any]) -> None:
    st.header("Triage Result")
    incident = result.get("incident")
    classification = result.get("classification")
    if incident is not None:
        st.subheader(f"{incident.title}  ·  `{incident.incident_id}`")
        st.caption(f"{incident.environment.value} · {incident.service} · source: {incident.source}")

    cols = st.columns(4)
    if classification is not None:
        cols[0].metric("Type", classification.incident_type.value)
        cols[1].metric("Priority", classification.priority.value)
        cols[2].metric("Confidence", f"{classification.confidence:.0%}")
    approval = result.get("approval")
    if approval is not None:
        cols[3].metric("Approval", "Approved" if approval.approved else "Rejected")

    report: IncidentReport | None = result.get("incident_report")
    if report is not None:
        st.markdown("---")
        st.markdown(render_markdown_report(report))
        col_a, col_b = st.columns(2)
        col_a.download_button(
            "Download report (Markdown)",
            data=render_markdown_report(report),
            file_name=f"{report.incident_id}_report.md",
            mime="text/markdown",
        )
        col_b.download_button(
            "Download report (JSON)",
            data=report.model_dump_json(indent=2),
            file_name=f"{report.incident_id}_report.json",
            mime="application/json",
        )
    else:
        if result.get("errors"):
            st.warning("No incident report was produced because the pipeline hit errors (see below).")
        else:
            st.warning("No incident report was produced (the incident may have been auto-resolved without a full investigation).")

    with st.expander("Raw JSON"):
        st.json(result)

    if result.get("errors"):
        st.error("Pipeline errors:\n" + "\n".join(f"- {e}" for e in result["errors"]))


def _render_saved_run(active: dict[str, Any]) -> None:
    """Re-render a completed run's three-zone layout from saved data (no re-stream)."""
    st.markdown("## Live execution")
    topology = get_graph_topology(triage_graph)
    panel_h = _panel_height(topology)
    col_main, col_detail = st.columns([3, 1.4])
    with col_main:
        st.markdown('<div class="it-zone-title">Graph canvas</div>', unsafe_allow_html=True)
        with st.container(height=panel_h, border=True):
            st.markdown(
                render_graph(
                    topology,
                    active["node_states"],
                    active.get("subagent_states", {}),
                    run_progress={"started": True, "completed": bool(active.get("completed"))},
                ),
                unsafe_allow_html=True,
            )
            st.markdown('<div class="it-zone-title">Execution timeline</div>', unsafe_allow_html=True)
            st.markdown(
                render_timeline(active["events"], active["node_order"]),
                unsafe_allow_html=True,
            )
    with col_detail:
        st.markdown('<div class="it-zone-title">Active node &middot; detail</div>', unsafe_allow_html=True)
        order = active.get("node_order", [])
        default_index = max(len(order) - 1, 0)
        with st.container(height=panel_h, border=True):
            # Manual override: the user picks which node to inspect; this
            # selection persists until they change it (auto-follow only applies
            # while a *live* run is streaming).
            label = st.selectbox("Inspect node", order, index=default_index,
                                 key=f"detail_node_{active['run_id']}")
            event = _merged_event(active["events"], label) if label else None
            st.markdown(
                render_detail(event) if event else '<span class="it-muted">No node selected.</span>',
                unsafe_allow_html=True,
            )

    st.markdown("---")
    if active.get("final_state"):
        _render_final_result(active["final_state"])
    if active.get("error"):
        st.error(f"Triage failed: {active['error']}")


def _render_run_history() -> None:
    st.sidebar.markdown("### Run history")
    runs = st.session_state.get("runs", [])
    if not runs:
        st.sidebar.caption("No runs yet.")
        return
    for run in runs:
        if run.get("error"):
            mark = "❌"
        elif run.get("completed"):
            mark = "✅"
        else:
            mark = "⏳"
        label = f"{mark} {run.get('title') or run['run_id'][:8]}"
        if st.sidebar.button(label, key=f"hist_{run['run_id']}"):
            saved = st.session_state.setdefault("_run_data", {}).get(run["run_id"])
            if saved is not None:
                st.session_state["active_run"] = saved
                st.rerun()


def main() -> None:
    st.set_page_config(page_title="Incident Triage", page_icon="🚨", layout="wide")
    st.markdown(theme.inject_css(), unsafe_allow_html=True)

    st.title("🚨 Incident Triage")
    st.caption("Provide an incident and run it through the triage LangGraph pipeline.")

    deps = _render_sidebar()
    _render_run_history()
    st.session_state["deps"] = deps

    samples = _load_samples()
    form_tab, json_tab = st.tabs(["Guided form", "JSON"])
    with form_tab:
        _render_form_tab(samples)
    with json_tab:
        _render_json_tab(samples)

    # After the intake form, either stream a freshly-requested run or re-render
    # the most recent completed run (so widget interactions don't re-run the graph).
    if st.session_state.pop("_run_requested", False):
        pending = st.session_state.pop("_pending_input", None)
        if pending is not None:
            _execute_run(pending, deps)
    elif st.session_state.get("active_run"):
        _render_saved_run(st.session_state["active_run"])


main()
