"""Generate a PNG visualization of the triage LangGraph workflow.

Writes docs/triage_graph.png so the orchestration can be reviewed visually.

Usage:
    python scripts/generate_graph_png.py

Rendering strategy (first that works wins):
1. Mermaid rendering via langgraph's ``draw_mermaid_png()`` (no local deps).
2. Graphviz ``draw_png()`` (requires the graphviz system binary).
3. Fallback: saves the raw Mermaid definition to docs/triage_graph.mmd so it
   can be rendered by any Mermaid-compatible viewer.
"""
from __future__ import annotations

from pathlib import Path

from app.graph.workflow import triage_graph

DOCS = Path(__file__).resolve().parent.parent / "docs"


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    graph_def = triage_graph.get_graph()

    try:
        png_bytes = graph_def.draw_mermaid_png()
        out = DOCS / "triage_graph.png"
        out.write_bytes(png_bytes)
        print(f"Graph PNG written to {out} ({len(png_bytes)} bytes) [mermaid]")
        return
    except Exception as exc:  # noqa: BLE001 -- fall through to graphviz
        print(f"mermaid rendering unavailable ({exc}); trying graphviz...")

    try:
        path = graph_def.draw_png(str(DOCS / "triage_graph.png"))
        print(f"Graph PNG written to {path} [graphviz]")
        return
    except Exception as exc:  # noqa: BLE001
        print(f"graphviz rendering unavailable ({exc}); writing mermaid source.")

    mmd = DOCS / "triage_graph.mmd"
    mmd.write_text(graph_def.draw_mermaid(), encoding="utf-8")
    print(f"Mermaid definition written to {mmd} (render with any Mermaid viewer)")


if __name__ == "__main__":
    main()
