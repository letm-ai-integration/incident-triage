"""Reusable LangGraph graph-construction infrastructure.

This module is the *generic* graph boundary. It knows nothing about incident
triage, classification, RCA or notifications. Application-specific assembly
belongs in :mod:`app.graph.workflow`.

Public API
----------
* :func:`createGraph` — create a new graph construction context
* :func:`addNode` — register a node
* :func:`addEdge` — register a directed edge
* :func:`addConditionalEdge` — register a router-based conditional edge
* :func:`compileGraph` — compile a constructed graph
* :func:`validateGraph` — validate a constructed graph
* :func:`START` / :func:`END` — graph entry/exit markers

The builder is explicitly *not* a singleton: every graph gets its own
context, which allows multiple independent graphs, testing and composition.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from typing import Any

from langgraph.graph import END, START, StateGraph

StateT = Any
NodeFn = Callable[..., Any]
RouterFn = Callable[..., Any]

START_NODE = START
END_NODE = END

# Human-readable aliases used in error messages.
_START_NAME = "__start__"
_END_NAME = "__end__"


class GraphError(Exception):
    """Raised for invalid graph construction operations."""


class DuplicateNodeError(GraphError):
    """Raised when a node is registered more than once."""


class InvalidNodeError(GraphError):
    """Raised when a node name is empty or not a string."""


class InvalidEdgeError(GraphError):
    """Raised when an edge references unknown nodes."""


class InvalidConditionalEdgeError(GraphError):
    """Raised when a conditional edge is malformed."""


@dataclass
class GraphContext[StateT]:
    """Mutable construction context for a single graph.

    Wraps a LangGraph :class:`StateGraph` together with bookkeeping the builder
    uses for validation and compilation. Never share a context across graphs.
    """

    state_schema: type[StateT]
    name: str = "graph"
    graph: StateGraph[Any] = field(init=False)
    nodes: set[str] = field(default_factory=set)
    edges: list[tuple[str, str]] = field(default_factory=list)
    checkpointer: Any | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.graph = StateGraph(self.state_schema)


def createGraph[StateT](
    state_schema: type[StateT],
    *,
    name: str = "graph",
    checkpointer: Any | None = None,
    config: dict[str, Any] | None = None,
) -> GraphContext[StateT]:
    """Create a new graph construction context.

    Parameters
    ----------
    state_schema:
        The TypedDict (or Pydantic model) that defines graph state.
    name:
        Optional graph name used for telemetry/debugging.
    checkpointer:
        Optional LangGraph checkpointer for checkpointing + interrupt/resume.
    config:
        Optional generic graph configuration.

    Returns
    -------
    GraphContext[StateT]
        A fresh, independent graph context. No nodes or edges are added here;
        that is the caller's responsibility.
    """
    return GraphContext(
        state_schema=state_schema,
        name=name,
        checkpointer=checkpointer,
        config=config or {},
    )


def addNode[StateT](
    context: GraphContext[StateT],
    name: str,
    node: NodeFn,
    *,
    metadata: dict[str, Any] | None = None,
) -> GraphContext[StateT]:
    """Register a node on ``context``.

    Supports sync and async callables. Validates the node name and rejects
    duplicate registrations.

    Returns
    -------
    GraphContext[StateT]
        The same context, for chaining.
    """
    _validate_node_name(name)
    if name in context.nodes:
        raise DuplicateNodeError(f"duplicate node '{name}'")
    if not callable(node):
        raise InvalidNodeError(f"node '{name}' is not callable")
    context.graph.add_node(name, node, metadata=metadata)
    context.nodes.add(name)
    return context


def addEdge[StateT](
    context: GraphContext[StateT],
    source: str,
    target: str,
) -> GraphContext[StateT]:
    """Register a directed edge ``source -> target``.

    ``source`` may be :data:`START`; ``target`` may be :data:`END`. Both may
    also be previously registered node names.

    Returns
    -------
    GraphContext[StateT]
        The same context, for chaining.
    """
    source_key = _to_langgraph_key(source)
    target_key = _to_langgraph_key(target)
    _validate_edge_endpoints(context, source, target)
    context.graph.add_edge(source_key, target_key)
    context.edges.append((source_key, target_key))
    return context


def addConditionalEdge[StateT](
    context: GraphContext[StateT],
    source: str,
    router: RouterFn,
    path_map: dict[Hashable, str] | None = None,
) -> GraphContext[StateT]:
    """Register a conditional edge driven by ``router``.

    The ``router`` callable receives the state and returns a key. ``path_map``
    maps those keys to node names or :data:`END`.

    Returns
    -------
    GraphContext[StateT]
        The same context, for chaining.
    """
    if source not in context.nodes:
        raise InvalidConditionalEdgeError(
            f"conditional edge source '{source}' is not a registered node"
        )
    if not callable(router):
        raise InvalidConditionalEdgeError(
            f"conditional edge router for '{source}' is not callable"
        )
    normalized: dict[Hashable, str] | None = None
    if path_map is not None:
        normalized = {key: _to_langgraph_key(value) for key, value in path_map.items()}
    context.graph.add_conditional_edges(source, router, path_map=normalized)
    return context


def compileGraph[StateT](
    context: GraphContext[StateT],
    *,
    checkpointer: Any | None = None,
    **kwargs: Any,
) -> Any:
    """Compile the constructed graph.

    Uses the context's checkpointer unless an explicit one is supplied. Extra
    keyword arguments are forwarded to LangGraph's ``compile``.

    Returns
    -------
    Any
        A compiled LangGraph application.
    """
    validateGraph(context)
    resolved_checkpointer = (
        checkpointer if checkpointer is not None else context.checkpointer
    )
    return context.graph.compile(checkpointer=resolved_checkpointer, **kwargs)


def validateGraph[StateT](context: GraphContext[StateT]) -> None:
    """Validate that ``context`` describes a compilable graph.

    Checks for at least one node, reachable start, and well-formed edges.
    """
    if not context.nodes:
        raise GraphError(f"graph '{context.name}' has no nodes")
    starts = [s for s, _ in context.edges if s == _START_NAME]
    if not starts:
        raise GraphError(f"graph '{context.name}' has no edge from START")
    for source, target in context.edges:
        _validate_edge_endpoints(context, source, target)


def _validate_node_name(name: str) -> None:
    if not isinstance(name, str) or not name.strip():
        raise InvalidNodeError("node name must be a non-empty string")


def _to_langgraph_key(name: str) -> str:
    return _END_NAME if name == "END" else _START_NAME if name == "START" else name


def _validate_edge_endpoints[StateT](
    context: GraphContext[StateT], source: str, target: str
) -> None:
    valid_start = source == _START_NAME or source in context.nodes
    valid_end = target == _END_NAME or target in context.nodes
    if not valid_start:
        raise InvalidEdgeError(
            f"edge source '{source}' is not START and not a registered node"
        )
    if not valid_end:
        raise InvalidEdgeError(
            f"edge target '{target}' is not END and not a registered node"
        )


__all__ = [
    "END",
    "START",
    "DuplicateNodeError",
    "GraphContext",
    "GraphError",
    "InvalidConditionalEdgeError",
    "InvalidEdgeError",
    "InvalidNodeError",
    "addConditionalEdge",
    "addEdge",
    "addNode",
    "compileGraph",
    "createGraph",
    "validateGraph",
]
