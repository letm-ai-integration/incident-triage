"""Render the execution timeline (vertical stepper), one row per node.

Rows are native-HTML (collapsible via ``<details>``) so the whole timeline can be
re-rendered into an ``st.empty()`` / ``st.container()`` placeholder on every
event during a live run and between runs. Each row shows the node's status pill,
duration, a one-line output preview, and -- when expanded -- its full input /
output snapshots.
"""

from __future__ import annotations

import html
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


def _duration_text(duration_ms: float | None, started_at: Any, ended_at: Any) -> str:
    if duration_ms is not None:
        if duration_ms < 1000:
            return f"{duration_ms:.0f} ms"
        return f"{duration_ms / 1000:.2f} s"
    if started_at is not None:
        return started_at.strftime("%H:%M:%S")
    return ""


def _merged(events: list[NodeEvent], node_name: str) -> NodeEvent | None:
    running: NodeEvent | None = None
    terminal: NodeEvent | None = None
    for event in events:
        if event.node_name != node_name:
            continue
        if event.status == "running":
            running = event
        elif event.status in ("success", "error"):
            terminal = event
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


def _row(event: NodeEvent) -> str:
    color = theme.status_color(event.status)
    label = _esc(theme.status_label(event.status))
    duration = _esc(_duration_text(event.duration_ms, event.started_at, event.ended_at))

    lines: list[str] = []
    if event.input_snapshot:
        lines.append("<details><summary>Input snapshot</summary>")
        lines.append(f"<pre>{_esc(_pretty(event.input_snapshot))}</pre></details>")
    if event.output_snapshot:
        lines.append("<details><summary>Output snapshot</summary>")
        lines.append(f"<pre>{_esc(_pretty(event.output_snapshot))}</pre></details>")
    if event.agent_trace:
        lines.append("<details><summary>Agent trace "
                     f"({len(event.agent_trace)} call(s))</summary>")
        lines.append(f"<pre>{_esc(_pretty(event.agent_trace))}</pre></details>")
    if event.error:
        lines.append(f'<div style="color:{theme.ACCENT}">Error: {_esc(event.error)}</div>')
    expander = "".join(lines)

    preview = ""
    if event.output_snapshot:
        preview = _esc(str(list(event.output_snapshot.keys())))

    return (
        f'<div style="border-left:3px solid {color};padding:6px 10px;margin:6px 0;'
        f'background:{theme.SURFACE};border-radius:6px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span><span class="it-status-pill" style="background:{color}">{label}</span> '
        f'&nbsp;<b style="color:{theme.TEXT}">{_esc(event.node_name)}</b> '
        f'<span class="it-muted">({len(event.agent_trace)} trace)</span></span>'
        f'<span class="it-duration">{duration}</span></div>'
        f'<div class="it-muted">{preview}</div>{expander}</div>'
    )


def render_timeline(events: list[NodeEvent], node_order: list[str] | None = None) -> str:
    """Return an HTML string of the timeline stepper.

    ``events`` is the append-only event log; ``node_order`` is the ordered node
    names (defaults to first-execution order). One row is rendered per node by
    fusing its ``running`` (input) and terminal (output/trace) events.
    """
    if node_order is None:
        node_order = []
        for event in events:
            if event.node_name not in node_order:
                node_order.append(event.node_name)

    rows = []
    for node_name in node_order:
        event = _merged(events, node_name)
        if event is not None:
            rows.append(_row(event))
    if not rows:
        return '<span class="it-muted">No execution events yet.</span>'
    return "".join(rows)
