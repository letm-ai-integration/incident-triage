# Graph introspection helpers for the UI.
# The UI should always derive the diagram from the live graph, not hardcode it,
# so the diagram stays in sync if a node/edge is added/removed/renamed.

from __future__ import annotations

from typing import Any

# LangGraph's ``get_graph()`` drawable uses these sentinel names for START/END.
_START = "__start__"
_END = "__end__"


def get_graph_topology(graph: Any) -> dict[str, Any]:
    """Return ``{nodes, edges, conditional_edges}`` describing a LangGraph graph.

    ``graph`` may be a compiled graph (``triage_graph``) or an uncompiled
    ``StateGraph`` -- both expose ``get_graph()`` returning a drawable with
    ``.nodes`` (a mapping) and ``.edges`` (a list of ``Edge`` objects). It is
    derived entirely from LangGraph introspection so it always matches reality.
    """
    drawable = graph.get_graph() if hasattr(graph, "get_graph") else graph

    nodes: list[str] = []
    for name in getattr(drawable, "nodes", {}):
        if name in (_START, _END):
            continue
        nodes.append(str(name))

    edges: list[dict[str, Any]] = []
    conditional_edges: dict[str, dict[str, str]] = {}

    for edge in getattr(drawable, "edges", []):
        # Normalise LangGraph's "__start__" / "__end__" sentinels to human
        # readable "START" / "END", but ALWAYS keep the real source/target name
        # for every other edge. (Mapping non-sentinel edges to START/END was the
        # bug that collapsed the whole graph into one START->END line.)
        if edge.source == _START:
            source = "START"
        elif edge.source == _END:
            source = "END"
        else:
            source = edge.source
        if edge.target == _START:
            target = "START"
        elif edge.target == _END:
            target = "END"
        else:
            target = edge.target

        label = getattr(edge, "data", None)
        is_conditional = bool(getattr(edge, "conditional", False))

        if is_conditional:
            conditional_edges.setdefault(str(edge.source), {})[str(label)] = str(target)
        edges.append(
            {
                "source": source,
                "target": target,
                "label": str(label) if label is not None else None,
                "conditional": is_conditional,
            }
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "conditional_edges": conditional_edges,
    }


__all__ = ["get_graph_topology"]
