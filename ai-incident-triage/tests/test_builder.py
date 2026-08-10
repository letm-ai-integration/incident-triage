"""Tests for the generic graph builder.

These tests deliberately use arbitrary nodes (``node_a``, ``node_b``, ...) to
prove the builder is genuinely reusable and has no incident-specific knowledge.
"""

from __future__ import annotations

import asyncio
from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.graph.builder import (
    END,
    START,
    DuplicateNodeError,
    GraphError,
    InvalidConditionalEdgeError,
    InvalidEdgeError,
    InvalidNodeError,
    addConditionalEdge,
    addEdge,
    addNode,
    compileGraph,
    createGraph,
    validateGraph,
)


class CounterState(TypedDict, total=False):
    value: int


def node_a(state: CounterState) -> dict:
    return {"value": state.get("value", 0) + 1}


async def node_b(state: CounterState) -> dict:
    return {"value": state.get("value", 0) + 10}


def _make_counter_graph():
    graph = createGraph(CounterState, name="counter")
    addNode(graph, "node_a", node_a)
    addNode(graph, "node_b", node_b)
    return graph


class TestCreateGraph:
    def test_create_graph_returns_context(self) -> None:
        graph = createGraph(CounterState)
        assert graph.name == "graph"
        assert graph.state_schema is CounterState
        assert graph.nodes == set()

    def test_create_graph_accepts_name_and_checkpointer(self) -> None:
        saver = InMemorySaver()
        graph = createGraph(CounterState, name="custom", checkpointer=saver)
        assert graph.name == "custom"
        assert graph.checkpointer is saver

    def test_multiple_graphs_are_independent(self) -> None:
        g1 = createGraph(CounterState, name="g1")
        g2 = createGraph(CounterState, name="g2")
        addNode(g1, "node_a", node_a)
        assert "node_a" in g1.nodes
        assert g2.nodes == set()


class TestAddNode:
    def test_add_node(self) -> None:
        graph = _make_counter_graph()
        assert graph.nodes == {"node_a", "node_b"}

    def test_duplicate_node_raises(self) -> None:
        graph = _make_counter_graph()
        with pytest.raises(DuplicateNodeError):
            addNode(graph, "node_a", node_a)

    def test_empty_name_raises(self) -> None:
        graph = createGraph(CounterState)
        with pytest.raises(InvalidNodeError):
            addNode(graph, "", node_a)

    def test_non_callable_raises(self) -> None:
        graph = createGraph(CounterState)
        with pytest.raises(InvalidNodeError):
            addNode(graph, "node_a", "not-a-callable")  # type: ignore[arg-type]


class TestAddEdge:
    def test_add_edge(self) -> None:
        graph = _make_counter_graph()
        addEdge(graph, START, "node_a")
        addEdge(graph, "node_a", "node_b")
        assert ("__start__", "node_a") in graph.edges
        assert ("node_a", "node_b") in graph.edges

    def test_invalid_source_raises(self) -> None:
        graph = _make_counter_graph()
        with pytest.raises(InvalidEdgeError):
            addEdge(graph, "ghost", "node_b")

    def test_invalid_target_raises(self) -> None:
        graph = _make_counter_graph()
        with pytest.raises(InvalidEdgeError):
            addEdge(graph, "node_a", "ghost")

    def test_edge_to_end(self) -> None:
        graph = _make_counter_graph()
        addEdge(graph, "node_b", END)
        assert ("node_b", "__end__") in graph.edges


class TestConditionalEdge:
    def test_add_conditional_edge(self) -> None:
        graph = _make_counter_graph()
        addConditionalEdge(
            graph,
            "node_b",
            lambda state: "end",
            path_map={"end": END},
        )

    def test_conditional_edge_unknown_source_raises(self) -> None:
        graph = _make_counter_graph()
        with pytest.raises(InvalidConditionalEdgeError):
            addConditionalEdge(graph, "ghost", lambda state: "end")

    def test_conditional_edge_non_callable_router_raises(self) -> None:
        graph = _make_counter_graph()
        with pytest.raises(InvalidConditionalEdgeError):
            addConditionalEdge(graph, "node_b", "not-a-callable")  # type: ignore[arg-type]


class TestValidation:
    def test_validate_empty_graph_raises(self) -> None:
        graph = createGraph(CounterState)
        with pytest.raises(GraphError):
            validateGraph(graph)

    def test_validate_no_start_edge_raises(self) -> None:
        graph = _make_counter_graph()
        addEdge(graph, "node_a", "node_b")
        with pytest.raises(GraphError):
            validateGraph(graph)


class TestCompileGraph:
    def test_compile_and_run_sync_and_async_nodes(self) -> None:
        async def run() -> None:
            graph = _make_counter_graph()
            addEdge(graph, START, "node_a")
            addEdge(graph, "node_a", "node_b")
            compiled = compileGraph(graph)
            result = await compiled.ainvoke({"value": 0})
            assert result["value"] == 11

        asyncio.run(run())

    def test_compile_with_checkpointer(self) -> None:
        async def run() -> None:
            saver = InMemorySaver()
            graph = _make_counter_graph()
            addEdge(graph, START, "node_a")
            addEdge(graph, "node_a", "node_b")
            compiled = compileGraph(graph, checkpointer=saver)
            cfg = {"configurable": {"thread_id": "t1"}}
            result = await compiled.ainvoke({"value": 0}, cfg)
            assert result["value"] == 11

        asyncio.run(run())


class TestComposition:
    """Prove the builder composes arbitrary graphs end-to-end.

    start -> node_a -> node_b -> node_c -> end, with a conditional router.
    """

    def test_simple_dag(self) -> None:
        async def run() -> None:
            graph = createGraph(CounterState, name="simple_dag")
            addNode(graph, "node_a", node_a)
            addNode(graph, "node_b", node_b)
            addEdge(graph, START, "node_a")
            addEdge(graph, "node_a", "node_b")
            addEdge(graph, "node_b", END)
            compiled = compileGraph(graph)
            result = await compiled.ainvoke({"value": 0})
            assert result["value"] == 11

        asyncio.run(run())

    def test_conditional_dag(self) -> None:
        def router(state: CounterState) -> str:
            return "end" if state["value"] >= 12 else "node_a"

        async def run() -> None:
            graph = createGraph(CounterState, name="conditional_dag")
            addNode(graph, "node_a", node_a)
            addNode(graph, "node_b", node_b)
            addEdge(graph, START, "node_a")
            addEdge(graph, "node_a", "node_b")
            addConditionalEdge(
                graph, "node_b", router, {"node_a": "node_a", "end": END}
            )
            compiled = compileGraph(graph)

            result = await compiled.ainvoke({"value": 0})
            # node_a -> node_b (11) -> router -> node_a (12) -> node_b (22) -> end
            assert result["value"] == 22

        asyncio.run(run())
