"""Generate a PNG of the Investigation Orchestrator's sub-agent workflow.

Writes docs/investigation_orchestration.png so the investigation phase can be
reviewed visually and independently of the parent triage graph
(docs/triage_graph.png).

The image is generated programmatically from the ACTUAL compiled subgraph the
orchestrator executes (app/agents/investigation/subgraph.py) -- never
hand-drawn. It shows the three parallel sub-agent nodes (log_analysis,
kubernetes, runbook) fanning in to the synthesize_outcome aggregator. When
x-ray rendering works, the subgraph is drawn nested inside its single parent
entry point ("investigation_orchestrator"), mirroring how the parent graph
keeps the whole phase behind one node.

Usage:
    python scripts/generate_investigation_png.py

Rendering strategy (first that works wins):
1. Mermaid rendering of the x-rayed phase graph (no local deps).
2. Mermaid rendering of the plain phase subgraph.
3. Graphviz ``draw_png()`` (requires the graphviz system binary).
4. Fallback: saves the raw Mermaid definition to docs/investigation_orchestration.mmd.
"""
from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from app.agents.investigation.subgraph import (
    InvestigationPhaseState,
    investigation_phase_graph,
)

DOCS = Path(__file__).resolve().parent.parent / "docs"


def _orchestrator_view():
    """Wrap the compiled phase subgraph as one 'investigation_orchestrator'
    node so x-ray rendering shows the orchestrator containing its sub-agents.

    Uses LangGraph's native subgraph composition (a compiled graph registered
    directly as a node); this is a rendering-only view -- the production
    parent graph keeps its single plain ``investigation`` node.
    """
    builder = StateGraph(InvestigationPhaseState)
    builder.add_node("investigation_orchestrator", investigation_phase_graph)
    builder.add_edge(START, "investigation_orchestrator")
    builder.add_edge("investigation_orchestrator", END)
    return builder.compile()


def _render(graph_def, out: Path, label: str) -> bytes:
    png_bytes = graph_def.draw_mermaid_png()
    out.write_bytes(png_bytes)
    print(f"Investigation PNG written to {out} ({len(png_bytes)} bytes) [{label}]")
    return png_bytes


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    out = DOCS / "investigation_orchestration.png"

    try:
        _render(_orchestrator_view().get_graph(xray=True), out, "mermaid+xray")
        return
    except Exception as exc:  # noqa: BLE001 -- fall through to plain subgraph
        print(f"x-ray mermaid rendering unavailable ({exc}); trying plain subgraph...")

    try:
        _render(investigation_phase_graph.get_graph(), out, "mermaid")
        return
    except Exception as exc:  # noqa: BLE001 -- fall through to graphviz
        print(f"mermaid rendering unavailable ({exc}); trying graphviz...")

    try:
        path = investigation_phase_graph.get_graph().draw_png(str(out))
        print(f"Investigation PNG written to {path} [graphviz]")
        return
    except Exception as exc:  # noqa: BLE001
        print(f"graphviz rendering unavailable ({exc}); writing mermaid source.")

    mmd = DOCS / "investigation_orchestration.mmd"
    mmd.write_text(investigation_phase_graph.get_graph().draw_mermaid(), encoding="utf-8")
    print(f"Mermaid definition written to {mmd} (render with any Mermaid viewer)")


if __name__ == "__main__":
    main()
