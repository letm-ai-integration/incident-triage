"""Render the detail panel for a single node's execution.

Shows the raw input state slice, the raw output state slice, per-LLM/tool-call
``agent_trace`` (as a collapsible mini-timeline), and timing/error info. This is
what makes LLM-backed nodes legible instead of a black box.

Trace entries that are still in flight (no ``status`` yet -- e.g. the live view
of a currently-running node's sub-agent fan-out) are shown as amber *running*
with their elapsed-so-far duration.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import Any

from app.graph.events import NodeEvent
from app.ui import theme


def _esc(text: Any) -> str:
    return html.escape(str(text))


def _pretty(value: Any) -> str:
    import json

    try:
        return json.dumps(value, indent=2, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def _duration_text(duration_ms: float | None) -> str:
    if duration_ms is None:
        return "—"
    if duration_ms < 1000:
        return f"{duration_ms:.0f} ms"
    return f"{duration_ms / 1000:.2f} s"


def _entry_duration(call: dict[str, Any]) -> str:
    """Duration of a trace entry, or elapsed-so-far if it is still in flight."""
    if call.get("duration_ms") is not None:
        return _duration_text(call["duration_ms"])
    started = call.get("started_at")
    if started is not None and call.get("ended_at") is None:
        if isinstance(started, str):
            try:
                started = datetime.fromisoformat(started)
            except ValueError:
                started = None
        if isinstance(started, datetime):
            elapsed = (datetime.now(UTC) - started).total_seconds() * 1000.0
            return f"{_duration_text(elapsed)} (so far)"
    return "—"


def _agent_trace_svg(trace: list[dict[str, Any]]) -> str:
    if not trace:
        return '<div class="it-muted">No LLM/tool activity captured for this node '
        '(deterministic step, or LLM not used / callbacks not wired).</div>'

    parts = []
    _TYPE_LABEL = {"llm_call": "LLM call", "tool_call": "tool", "subagent": "sub-agent"}
    for i, call in enumerate(trace, start=1):
        ctype = call.get("type", "call")
        name = call.get("name", ctype)
        # No status yet == still in flight (live view of a running node).
        status = call.get("status") or "running"
        if status == "success":
            color = theme.EDGE_TRAVERSED
        elif status == "error":
            color = theme.ACCENT
        else:
            color = theme.STATUS_COLORS.get("running")
        duration = _entry_duration(call)
        type_label = _TYPE_LABEL.get(ctype, ctype)
        parts.append(
            f'<details style="margin:6px 0;border-left:3px solid {color};'
            f'padding:4px 10px;background:{theme.SURFACE_ALT};border-radius:6px;">'
            f"<summary style=\"cursor:pointer;\">#{i} "
            f'<span class="it-status-pill" style="background:{color}">{_esc(status or "call")}</span> '
            f'<b style="color:{theme.TEXT}">{_esc(name)}</b> '
            f'<span class="it-muted">({_esc(type_label)})</span> '
            f'<span class="it-duration">⏱ {_esc(duration)}</span></summary>'
        )
        if call.get("input") is not None:
            parts.append(f"<details><summary>input</summary>"
                         f"<pre>{_esc(_pretty(call['input']))}</pre></details>")
        if call.get("output") is not None:
            parts.append(f"<details><summary>output</summary>"
                         f"<pre>{_esc(_pretty(call['output']))}</pre></details>")
        if call.get("error"):
            parts.append(f'<div style="color:{theme.ACCENT}">{_esc(call["error"])}</div>')
        parts.append("</details>")
    return "".join(parts)


def render_detail(event: NodeEvent) -> str:
    """Return HTML for the detail panel of a (merged) ``NodeEvent``."""
    if event is None:
        return '<span class="it-muted">Select a node to inspect.</span>'

    color = theme.status_color(event.status)
    header = (
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span><span class="it-status-pill" style="background:{color}">'
        f'{_esc(theme.status_label(event.status))}</span> '
        f'<b style="color:{theme.TEXT};text-transform:none;">{_esc(event.node_name)}</b></span>'
        f'<span class="it-duration">⏱ {_esc(_duration_text(event.duration_ms))}</span></div>'
        f'<div class="it-muted">run {_esc(event.run_id)}</div>'
    )

    sections: list[str] = []
    if event.error:
        sections.append(f'<div style="background:{theme.ACCENT};color:#0b0f14;'
                        f'padding:6px 10px;border-radius:6px;margin:8px 0;">'
                        f'Error: {_esc(event.error)}</div>')
    if event.input_snapshot is not None:
        sections.append("<details open><summary>Input state slice</summary>"
                        f"<pre>{_esc(_pretty(event.input_snapshot))}</pre></details>")
    if event.output_snapshot is not None:
        sections.append("<details open><summary>Output state slice</summary>"
                        f"<pre>{_esc(_pretty(event.output_snapshot))}</pre></details>")
    if event.agent_trace:
        sections.append("<details open><summary>Agent trace "
                        f"({len(event.agent_trace)} call(s))</summary>")
        sections.append(_agent_trace_svg(event.agent_trace))
        sections.append("</details>")
    if not sections:
        sections.append('<span class="it-muted">No snapshots captured.</span>')

    return (
        f'<div style="background:{theme.SURFACE};border:1px solid {theme.BORDER};'
        f'border-radius:8px;padding:10px;">{header}<hr style="border-color:{theme.BORDER}">'
        f'{"".join(sections)}</div>'
    )
