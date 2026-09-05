"""Render the triage graph topology as a live-updating SVG.

Used by the "GRAPH CANVAS" zone. The node names / edges come from LangGraph
introspection (``get_graph_topology``) so the diagram always matches the real
graph; only the node *positions* are fixed for layout. Each node is coloured by
its latest status (gray=pending, amber=running, green=success, red=error) and
edges that have been traversed are highlighted so conditional branches (e.g.
"auto_resolve" vs "full_investigation") are visible at a glance.

No external graph-viz dependency is required -- the SVG is generated directly.
"""

from __future__ import annotations

import html
from typing import Any

from app.ui import theme

# Node box geometry.
_NODE_W = 160
_NODE_H = 48
_PILL_W = 118
_PILL_H = 20
_PILL_GAP = 8
_CENTER_X = 300
_MARGIN_Y = 38
_ROW_GAP = 38
_LANE_SLOT = 22
_RIGHT_LANE_BASE = 560
_LEFT_LANE_BASE = _CENTER_X - _NODE_W / 2 - 56


def _status(value: Any) -> str:
    """Extract a status string from a NodeEvent or a status-bearing dict."""
    if value is None:
        return "pending"
    if isinstance(value, dict):
        return str(value.get("status", "pending"))
    return str(getattr(value, "status", "pending"))


def _esc(text: Any) -> str:
    return html.escape(str(text))


def _node_svg(name: str, cx: float, cy: float, status: str) -> str:
    color = theme.status_color(status)
    x = cx - _NODE_W / 2
    y = cy - _NODE_H / 2
    pulse = ' class="it-running"' if status == "running" else ""
    glyph = "⟳ " if status == "running" else ""
    return (
        f'<g{pulse}><rect x="{x:.0f}" y="{y:.0f}" width="{_NODE_W}" height="{_NODE_H}" rx="8" '
        f'fill="{theme.SURFACE}" stroke="{color}" stroke-width="2"/>'
        f'<circle cx="{x + 12:.0f}" cy="{cy:.0f}" r="4" fill="{color}"/>'
        f'<text x="{x + 24:.0f}" y="{cy - 3:.0f}" fill="{theme.TEXT}" font-size="13" '
        f'font-family="ui-monospace,monospace" font-weight="600">{_esc(name)}</text>'
        f'<text x="{x + 24:.0f}" y="{cy + 13:.0f}" fill="{theme.MUTED}" font-size="10">'
        f'{_esc(glyph + theme.status_label(status))}</text></g>'
    )


def _ellipse_svg(name: str, cx: float, cy: float, status: str) -> str:
    color = theme.status_color(status)
    pulse = ' class="it-running"' if status == "running" else ""
    glyph = "⟳ " if status == "running" else ""
    return (
        f'<g{pulse}><ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="38" ry="17" fill="{theme.SURFACE}" '
        f'stroke="{color}" stroke-width="2"/>'
        f'<text x="{cx:.0f}" y="{cy - 1:.0f}" fill="{theme.TEXT}" font-size="11" '
        f'text-anchor="middle" font-family="ui-monospace,monospace" font-weight="700">'
        f'{_esc(name)}</text>'
        f'<text x="{cx:.0f}" y="{cy + 12:.0f}" fill="{color}" font-size="9" '
        f'text-anchor="middle" font-family="ui-monospace,monospace">'
        f'{_esc(glyph + theme.status_label(status))}</text></g>'
    )


def _pill_svg(name: str, cx: float, cy: float, status: str) -> str:
    color = theme.status_color(status)
    x = cx - _PILL_W / 2
    y = cy - _PILL_H / 2
    pulse = ' class="it-running"' if status == "running" else ""
    glyph = "⟳ " if status == "running" else ""
    return (
        f'<g{pulse}><rect x="{x:.0f}" y="{y:.0f}" width="{_PILL_W}" height="{_PILL_H}" rx="4" '
        f'fill="{theme.SURFACE_ALT}" stroke="{color}" stroke-width="1.5"/>'
        f'<circle cx="{x + 10:.0f}" cy="{cy:.0f}" r="3" fill="{color}"/>'
        f'<text x="{x + 18:.0f}" y="{cy + 4:.0f}" fill="{theme.TEXT}" font-size="10" '
        f'font-family="ui-monospace,monospace">{_esc(glyph + name)}</text></g>'
    )


def _edge_path(points: list[tuple[float, float]], color: str, dashed: bool,
               label: str | None = None, label_dx: float = 0) -> str:
    dash = ' stroke-dasharray="6,4"' if dashed else ""
    pts = " ".join(f"{x:.0f},{y:.0f}" for x, y in points)
    label_svg = ""
    if label:
        mx, my = points[len(points) // 2]
        label_svg = (
            f'<text x="{mx + label_dx:.0f}" y="{my - 6:.0f}" fill="{theme.MUTED}" '
            f'font-size="9" text-anchor="middle" '
            f'font-family="ui-monospace,monospace">{_esc(label)}</text>'
        )
    return (
        f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"{dash} '
        f'marker-end="url(#arrow)"/>' + label_svg
    )


def _child_names(node: str, node_states: dict[str, Any],
                 subagent_states: dict[str, Any]) -> list[str]:
    """Names of a node's sub-agent calls (live bus states, else the node event).

    Used to draw a fan-out cluster, so any node that records ``subagent`` trace
    entries renders its children generically -- not just ``investigation``.
    """
    names = list(subagent_states.get(node, {}).keys())
    if names:
        return names
    event = node_states.get(node)
    if event is None:
        return []
    trace = getattr(event, "agent_trace", None) or []
    return [str(t.get("name")) for t in trace if isinstance(t, dict) and t.get("type") == "subagent"]


def _layout(topology: dict[str, Any]) -> tuple[dict[str, int], dict[str, float], float]:
    """Assign each node a topological level and a centre-y on the vertical spine.

    Levels come from the *longest path from START* over the acyclic forward-edge
    set (the one cycle, verification -> investigation, is detected and excluded),
    which correctly places branches and merges. START sits alone at level 0 and
    END one level after the last node that feeds it.
    """
    edges = topology.get("edges", [])
    nodes = set(topology.get("nodes", [])) | {"START", "END"}
    adj: dict[str, list[str]] = {}
    for e in edges:
        adj.setdefault(e["source"], []).append(e["target"])

    # DFS colouring detects the single back-edge (verification -> investigation).
    #
    # The DFS MUST start from START (then any unvisited nodes, sorted) and walk
    # neighbours in sorted order so it is deterministic. The loop-back edge is
    # only discoverable as a back-edge if the DFS enters the loop through its
    # real entry point: starting at START we reach investigation via
    # classification, so verification -> investigation is flagged while
    # investigation is still on the recursion stack. Starting the DFS at an
    # arbitrary set-ordered node (e.g. rca_report) instead flags a *different*
    # edge of the same cycle (investigation_summary -> rca_report), which then
    # gets excluded from the level computation below -- rca_report pops from the
    # Kahn queue at level 0 and the whole spine is drawn out of order.
    color: dict[str, int] = {}
    back: set[tuple[str, str]] = set()

    def _dfs(node: str) -> None:
        color[node] = 1
        for nxt in sorted(adj.get(node, [])):
            if color.get(nxt) == 1:
                back.add((node, nxt))
            elif color.get(nxt, 0) == 0:
                _dfs(nxt)
        color[node] = 2

    for node in ["START", *sorted(nodes - {"START"})]:
        if color.get(node, 0) == 0:
            _dfs(node)

    # Longest-path level over the acyclic forward edges (Kahn topological sort).
    indeg = {n: 0 for n in nodes}
    fwd: dict[str, list[str]] = {}
    for e in edges:
        s, t = e["source"], e["target"]
        if (s, t) in back:
            continue
        fwd.setdefault(s, []).append(t)
        indeg[t] += 1

    from collections import deque
    queue = deque(sorted(n for n in nodes if indeg[n] == 0))
    level = {n: 0 for n in nodes}
    while queue:
        node = queue.popleft()
        for nxt in fwd.get(node, []):
            level[nxt] = max(level[nxt], level[node] + 1)
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    level["END"] = max([level[s] for e in edges if e["target"] == "END"] or [0]) + 1
    level["START"] = 0

    max_level = max(level.values())
    y_cent: dict[str, float] = {}
    cursor = _MARGIN_Y
    for lvl in range(max_level + 1):
        for n in sorted(nodes):
            if level[n] == lvl:
                y_cent[n] = cursor + _NODE_H / 2
        cursor += _NODE_H + _ROW_GAP
    height = cursor - _ROW_GAP + _MARGIN_Y
    return level, y_cent, height


def _half_h(name: str) -> float:
    """Half the drawn height of a node/START/END (used as edge anchor points)."""
    return 17.0 if name in ("START", "END") else _NODE_H / 2


def render_graph(
    topology: dict[str, Any],
    node_states: dict[str, Any],
    subagent_states: dict[str, Any] | None = None,
    run_progress: dict[str, bool] | None = None,
) -> str:
    """Return an SVG of ``topology`` laid out by topological level.

    ``subagent_states`` (``{parent_node: {subagent_name: status}}`` from the live
    ``RunEventBus``) colours the fan-out child pills, so a node that records
    ``subagent`` trace entries is drawn as a cluster.

    ``run_progress`` (``{"started": bool, "completed": bool}``) drives the
    structural START/END markers, which are *not* real nodes and get their own
    status semantics (`started` / `completed` / `idle`) rather than Pending.
    """
    subagent_states = subagent_states or {}
    run_progress = run_progress or {}
    started = bool(run_progress.get("started"))
    completed = bool(run_progress.get("completed"))
    all_edges = topology.get("edges", [])
    node_names = topology.get("nodes", [])
    level, y_cent, canvas_h = _layout(topology)

    HW = _NODE_W / 2

    ran: set[str] = set()
    running: set[str] = set()
    for name in node_names:
        st = _status(node_states.get(name))
        if st == "running":
            running.add(name)
        if st in ("success", "error"):
            ran.add(name)
    if ran:
        ran.add("END")

    # Assign lane slots to non-adjacent (branch / loop) edges so they route
    # around the central spine without overlapping each other.
    right_slot = left_slot = 0
    lane: dict[tuple[str, str], tuple[float, int]] = {}
    for e in all_edges:
        s, t = e["source"], e["target"]
        if s not in y_cent or t not in y_cent:
            continue
        if abs(level.get(t, 0) - level.get(s, 0)) != 1:
            if level[t] > level[s]:
                lane[(s, t)] = (_RIGHT_LANE_BASE + right_slot * _LANE_SLOT, 1)
                right_slot += 1
            else:
                lane[(s, t)] = (_LEFT_LANE_BASE - left_slot * _LANE_SLOT, -1)
                left_slot += 1

    parts: list[str] = [
        (
            f'<svg width="100%" viewBox="0 0 660 {canvas_h:.0f}" '
            f'style="background:{theme.BG};border:1px solid {theme.BORDER};border-radius:8px">'
        ),
        (
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            '<path d="M0,0 L10,5 L0,10 z" fill="context-stroke"/></marker></defs>'
        ),
    ]

    for e in all_edges:
        s, t = e["source"], e["target"]
        if s not in y_cent or t not in y_cent:
            continue
        if t in running:
            color = theme.EDGE_ACTIVE
        elif t in ran or s == "START":
            color = theme.EDGE_TRAVERSED
        else:
            color = theme.EDGE_DIM
        dashed = bool(e.get("conditional"))
        label = e.get("label")
        if abs(level.get(t, 0) - level.get(s, 0)) == 1:
            points = [(_CENTER_X, y_cent[s] + _half_h(s)), (_CENTER_X, y_cent[t] - _half_h(t))]
            label_dx = 16 if label else 0
        else:
            lx, _dir = lane.get((s, t), (_RIGHT_LANE_BASE, 1))
            sx = (_CENTER_X + HW) if lx > _CENTER_X else (_CENTER_X - HW)
            tx = (_CENTER_X + HW) if lx > _CENTER_X else (_CENTER_X - HW)
            points = [(sx, y_cent[s]), (lx, y_cent[s]), (lx, y_cent[t]), (tx, y_cent[t])]
            label_dx = 10 if lx > _CENTER_X else -10
        parts.append(_edge_path(points, color, dashed, label, label_dx))

    for name in node_names:
        cy = y_cent[name]
        cx = _CENTER_X
        children = _child_names(name, node_states, subagent_states)
        if children:
            pill_cx = _CENTER_X + HW + 22 + _PILL_W / 2
            top = cy - ((len(children) - 1) * (_PILL_H + _PILL_GAP)) / 2
            cbox_left = _CENTER_X - HW - 12
            cbox_right = pill_cx + _PILL_W / 2 + 12
            parts.append(
                f'<rect x="{cbox_left:.0f}" y="{cy - 24:.0f}" '
                f'width="{cbox_right - cbox_left:.0f}" height="{_NODE_H + 24:.0f}" rx="12" '
                f'fill="{theme.SURFACE_ALT}" stroke="{theme.BORDER}" stroke-dasharray="4,4" '
                f'stroke-width="1.5"/>'
            )
            for i, cname in enumerate(children):
                pcy = top + i * (_PILL_H + _PILL_GAP) + _PILL_H / 2
                status = subagent_states.get(name, {}).get(cname, "pending")
                parts.append(
                    f'<line x1="{_CENTER_X + HW + 4:.0f}" y1="{cy:.0f}" '
                    f'x2="{pill_cx - _PILL_W / 2 - 2:.0f}" y2="{pcy:.0f}" '
                    f'stroke="{theme.BORDER}" stroke-width="1"/>'
                )
                parts.append(_pill_svg(cname, pill_cx, pcy, status))
        parts.append(_node_svg(name, cx, cy, _status(node_states.get(name))))

    start_status = "started" if started else "idle"
    end_status = "completed" if completed else "idle"
    parts.append(_ellipse_svg("START", _CENTER_X, y_cent["START"], start_status))
    parts.append(_ellipse_svg("END", _CENTER_X, y_cent["END"], end_status))
    svg = "".join(parts) + "</svg>"
    return svg


def canvas_height(topology: dict[str, Any]) -> float:
    """The pixel height the SVG canvas occupies (used to align side panels).

    Both the graph canvas container and the Active node · detail panel use this
    same height so the two side-by-side panels visually match regardless of how
    much content is inside either one.
    """
    _, _, height = _layout(topology)
    return height

