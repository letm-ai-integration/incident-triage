# Builds and compiles the LangGraph graph.
#
# This module is the ONLY place ``StateGraph`` is instantiated directly. The
# public API is:
#
#   create_graph(state_schema=None)   -> StateGraph
#   add_node(graph, name, node)
#   add_edge(graph, source, target)
#   add_conditional_edge(graph, source, router_fn, path_map)
#   compile_graph(graph)              -> compiled graph
#   get_deps(config)                  -> injected dependency dict
#
# ``START`` and ``END`` are re-exported here so workflow modules never need to
# import langgraph internals themselves.
#
# v2 nodes: ingestion, classification, investigation, investigation_summary,
# rca_report, approval, verification, notification.
from __future__ import annotations

import functools
import logging
import re
from typing import Any, Callable, Mapping, Optional

from langgraph.graph import END, START, StateGraph

from app.graph.state import IncidentState

__all__ = [
    "GraphBuildError",
    "START",
    "END",
    "create_graph",
    "add_node",
    "add_edge",
    "add_conditional_edge",
    "compile_graph",
    "get_deps",
]


class GraphBuildError(Exception):
    """Raised when a graph is assembled with an invalid node/edge definition."""


logger = logging.getLogger(__name__)


def _wrap_node_with_logging(name: str, node: Callable) -> Callable:
    """Wrap a node so every graph execution logs that the node was accessed."""

    @functools.wraps(node)
    def _wrapped(state: Any, *args: Any, **kwargs: Any) -> Any:
        logger.info("[graph] -> node '%s' entered", name)
        try:
            result = node(state, *args, **kwargs)
        except Exception:
            logger.exception("[graph] node '%s' raised an exception", name)
            raise
        logger.info("[graph] <- node '%s' completed", name)
        return result

    return _wrapped


_NODE_NAMES_ATTR = "_graph_node_names"
_CONDITIONAL_SOURCES_ATTR = "_graph_conditional_sources"

_SNAKE_CASE_RE = re.compile(r"[a-z][a-z0-9_]*")


def _ensure_graph(graph: Any) -> None:
    if not isinstance(graph, StateGraph):
        raise GraphBuildError(
            f"expected a StateGraph created by create_graph(), got {type(graph).__name__}"
        )
    if not hasattr(graph, _NODE_NAMES_ATTR):
        raise GraphBuildError(
            "graph was not created by create_graph(); use builder.create_graph()"
        )


def _node_names(graph: StateGraph) -> set:
    return getattr(graph, _NODE_NAMES_ATTR)


def _is_start(node: Any) -> bool:
    return node is START or node == "START"


def _is_end(node: Any) -> bool:
    return node is END or node == "END"


def _validate_node_name(name: Any) -> None:
    if not isinstance(name, str) or not _SNAKE_CASE_RE.fullmatch(name):
        raise GraphBuildError(
            f"invalid node name {name!r}; names must be snake_case stage names "
            "(e.g. 'rca_report', not 'RCAReportNode')"
        )


def create_graph(state_schema: Optional[type] = None) -> StateGraph:
    """Instantiate a new, empty graph over the given state schema."""
    if state_schema is None:
        state_schema = IncidentState
    graph = StateGraph(state_schema)
    setattr(graph, _NODE_NAMES_ATTR, set())
    setattr(graph, _CONDITIONAL_SOURCES_ATTR, {})
    return graph


def add_node(graph: StateGraph, name: str, node: Callable) -> None:
    """Register ``node`` under the stage name ``name``."""
    _ensure_graph(graph)
    _validate_node_name(name)
    if name in _node_names(graph):
        raise GraphBuildError(f"duplicate node {name!r}: a node with this name is already registered")
    if not callable(node):
        raise GraphBuildError(f"node {name!r} must be callable, got {type(node).__name__}")
    graph.add_node(name, _wrap_node_with_logging(name, node))
    _node_names(graph).add(name)


def add_edge(graph: StateGraph, source: Any, target: Any) -> None:
    """Add an unconditional transition ``source -> target``.

    ``source``/``target`` are registered node names, or the ``START``/``END``
    sentinels.
    """
    _ensure_graph(graph)
    if not _is_start(source) and not _is_end(source) and source not in _node_names(graph):
        raise GraphBuildError(
            f"unknown node in edge: {source!r} is not a registered node (and not START/END)"
        )
    if not _is_start(target) and not _is_end(target) and target not in _node_names(graph):
        raise GraphBuildError(
            f"unknown node in edge: {target!r} is not a registered node (and not START/END)"
        )
    if (_is_start(source) and _is_start(target)) or (_is_end(source) and _is_end(target)):
        raise GraphBuildError(f"invalid edge {source!r} -> {target!r}: both endpoints are sentinels")
    graph.add_edge(source, target)


def add_conditional_edge(
    graph: StateGraph,
    source: str,
    router_fn: Callable[[Mapping[str, Any]], str],
    path_map: Mapping[str, Any],
) -> None:
    """Add a conditional transition governed by ``router_fn``.

    ``router_fn(state)`` returns one of the outcome keys in ``path_map``; the
    mapped value is the destination node name or ``END``.
    """
    _ensure_graph(graph)
    if source not in _node_names(graph):
        raise GraphBuildError(
            f"unknown node in conditional edge: {source!r} is not a registered node"
        )
    if not callable(router_fn):
        raise GraphBuildError(f"router for {source!r} must be callable, got {type(router_fn).__name__}")
    if not path_map:
        raise GraphBuildError(f"conditional edge from {source!r} needs a non-empty path_map")

    for outcome, target in path_map.items():
        if not isinstance(outcome, str) or not outcome:
            raise GraphBuildError(
                f"conditional edge from {source!r} has invalid outcome key {outcome!r}"
            )
        if not _is_end(target) and target not in _node_names(graph):
            raise GraphBuildError(
                f"conditional edge from {source!r} maps {outcome!r} to unknown node {target!r}"
            )

    sources = getattr(graph, _CONDITIONAL_SOURCES_ATTR)
    previous = sources.get(source, set())
    overlap = previous & set(path_map.keys())
    if overlap:
        raise GraphBuildError(
            f"conditional edge from {source!r} reuses outcome key(s) "
            f"{sorted(overlap)}; outcome keys must be unique per source node"
        )
    sources.setdefault(source, set()).update(path_map.keys())

    graph.add_conditional_edges(source, router_fn, dict(path_map))


def compile_graph(graph: StateGraph):
    """Validate and compile ``graph`` into an executable graph."""
    _ensure_graph(graph)
    try:
        return graph.compile()
    except Exception as exc:  # surface LangGraph build errors as GraphBuildError
        raise GraphBuildError(f"failed to compile graph: {exc}") from exc


def get_deps(config: Optional[Mapping[str, Any]] = None) -> dict:
    """Extract the dependency dict from a LangGraph ``config``.

    Nodes receive ``(state, config)`` from LangGraph; services/agents are
    injected through ``config["configurable"]["deps"]`` so tests and callers can
    override real dependencies per run without touching node internals.
    """
    if not config:
        return {}
    configurable = config.get("configurable")
    if isinstance(configurable, Mapping):
        deps = configurable.get("deps")
        if isinstance(deps, Mapping):
            return dict(deps)
    return {}
