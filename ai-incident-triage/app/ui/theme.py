"""Shared visual theme for the incident-triage Streamlit UI.

Single source of truth for the dark palette (with the red/coral accent from the
existing Run Options panel) so the new graph-canvas / timeline / detail-panel
zones don't visually clash with the untouched intake form.

Everything here is also used by the HTML/SVG renderers in ``render_graph`` /
``render_timeline`` / ``render_detail``.
"""

from __future__ import annotations

# -- Base palette -----------------------------------------------------------
BG = "#0e1117"
SURFACE = "#161b22"
SURFACE_ALT = "#1c2128"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#ff4b4b"  # coral/red accent (matches existing Run Options panel)
ACCENT_SOFT = "#ff7b72"

# -- Node status colours ----------------------------------------------------
STATUS_COLORS = {
    "pending": "#6e7681",     # gray
    "running": "#f0883e",     # amber
    "success": "#3fb950",     # green
    "error": "#ff4b4b",       # red
    "started": "#58a6ff",     # blue (structural START)
    "completed": "#a371f7",   # purple (structural END)
    "idle": "#484f58",        # neutral (START/END before a run begins)
}

STATUS_LABELS = {
    "pending": "Pending",
    "running": "Running",
    "success": "Success",
    "error": "Error",
    "started": "Started",
    "completed": "Completed",
    "idle": "Idle",
}

# Legend order (color dot + label) shown in the left rail under Run Options.
LEGEND_ITEMS = [
    ("pending", "Pending — not started"),
    ("running", "Running — executing"),
    ("success", "Success — completed"),
    ("error", "Error — failed"),
    ("started", "Started — run begun"),
    ("completed", "Completed — run finished"),
]

EDGE_TRAVERSED = "#3fb950"
EDGE_ACTIVE = "#f0883e"
EDGE_DIM = "#6e7681"


def status_color(status: str) -> str:
    """Return the hex colour for a node ``status`` string."""
    return STATUS_COLORS.get(status, STATUS_COLORS["pending"])


def status_label(status: str) -> str:
    """Return the human label for a ``status`` string."""
    return STATUS_LABELS.get(status, status.title())


def inject_css() -> str:
    """Return a ``<style>`` block to markdown once at the top of the app."""
    return f"""
<style>
  .it-status-pill {{
    display: inline-block; padding: 1px 8px; border-radius: 10px;
    font-size: 0.72rem; font-weight: 600; letter-spacing: .3px;
    color: #0b0f14; text-transform: uppercase;
  }}
  .it-duration {{ color: {MUTED}; font-size: 0.78rem; }}
  .it-zone-title {{ color: {ACCENT_SOFT}; font-size: 1.0rem; font-weight: 700; }}
  .it-muted {{ color: {MUTED}; }}
  .it-scroll {{
    border: 1px solid {BORDER}; border-radius: 8px;
    background: {SURFACE}; padding: 6px; overflow-y: auto;
  }}
  @keyframes itPulse {{
    0%, 100% {{ opacity: 1.0; }}
    50% {{ opacity: 0.35; }}
  }}
  .it-running {{ animation: itPulse 1.1s ease-in-out infinite; }}
</style>
"""


def legend_html() -> str:
    """A small compact legend mapping each status colour to its meaning."""
    chips = []
    for key, label in LEGEND_ITEMS:
        color = STATUS_COLORS[key]
        chips.append(
            f'<span style="display:flex;align-items:center;gap:5px;white-space:nowrap;">'
            f'<span style="width:10px;height:10px;border-radius:50%;'
            f'background:{color};display:inline-block;"></span>'
            f'<span style="color:{MUTED};font-size:0.75rem;">{label}</span></span>'
        )
    return (
        f'<div style="display:flex;flex-wrap:wrap;gap:8px 14px;'
        f'border:1px solid {BORDER};border-radius:8px;padding:8px 10px;">'
        + "".join(chips) + "</div>"
    )
