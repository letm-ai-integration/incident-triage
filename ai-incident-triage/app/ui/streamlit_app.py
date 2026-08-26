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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import streamlit as st

from app.config import get_settings
from app.domain.enums.environment import Environment
from app.domain.enums.priority import Priority
from app.domain.models.report import IncidentReport
from app.graph.workflow import triage_graph
from app.services.classification_service import classification_service
from app.services.investigation_service import investigation_service
from app.services.rca_report_service import rca_report_service, render_markdown_report

SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "incidents"
RECURSION_LIMIT = 50  # safety net on top of MAX_INVESTIGATION_RETRIES

st.set_page_config(page_title="Incident Triage", page_icon="🚨", layout="wide")


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

    deps: dict[str, Any] = {"auto_approve": auto_approve}
    if use_llm and llm_available:
        deps["classification_service"] = classification_service
        deps["investigation_service"] = investigation_service
        deps["rca_report_service"] = rca_report_service

    st.sidebar.caption(f"LLM provider configured: {'yes' if llm_available else 'no'}")
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
            _run_triage(_build_raw_input_from_form())


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
        _run_triage(raw_input)


def _run_triage(raw_input: dict[str, Any]) -> None:
    deps = st.session_state.get("deps", {"auto_approve": True})
    with st.spinner("Running triage pipeline..."):
        try:
            result = triage_graph.invoke(
                {"raw_input": raw_input},
                config={"configurable": {"deps": deps}, "recursion_limit": RECURSION_LIMIT},
            )
        except Exception as exc:  # noqa: BLE001 -- surface a short message, never a raw traceback
            st.error(f"Triage failed: {exc}")
            return
    st.session_state["result"] = result


def _render_results(result: dict[str, Any]) -> None:
    incident = result.get("incident")
    classification = result.get("classification")
    st.header("Triage Result")

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
        st.download_button(
            "Download report (Markdown)",
            data=render_markdown_report(report),
            file_name=f"{report.incident_id}_report.md",
            mime="text/markdown",
        )
        st.download_button(
            "Download report (JSON)",
            data=report.model_dump_json(indent=2),
            file_name=f"{report.incident_id}_report.json",
            mime="application/json",
        )
    else:
        st.warning("No incident report was produced (the incident may have been auto-resolved without a full investigation).")

    if result.get("errors"):
        st.error("Pipeline errors:\n" + "\n".join(f"- {e}" for e in result["errors"]))


def main() -> None:
    st.title("🚨 Incident Triage")
    st.caption("Provide an incident and run it through the triage LangGraph pipeline.")

    samples = _load_samples()
    st.session_state["deps"] = _render_sidebar()

    form_tab, json_tab = st.tabs(["Guided form", "JSON"])
    with form_tab:
        _render_form_tab(samples)
    with json_tab:
        _render_json_tab(samples)

    if "result" in st.session_state:
        st.markdown("## ")
        _render_results(st.session_state["result"])


main()
