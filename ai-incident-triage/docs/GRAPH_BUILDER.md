# Graph Builder — Reusable LangGraph Infrastructure

This document describes the generic graph-construction layer of the AI Incident
Triage project and how to use it.

## Architecture

```text
GENERIC GRAPH INFRASTRUCTURE
        app/graph/builder.py          (reusable, knows nothing about triage)
               │
APPLICATION-SPECIFIC WORKFLOW
        app/graph/workflow.py         (assembles the v2 triage graph)
               │
        app/graph/nodes/*.py          (thin orchestration adapters)
```

- **Agents** (`app/agents/`) provide capabilities.
- **Nodes** (`app/graph/nodes/`) adapt agent outputs to graph state.
- **Builder** (`app/graph/builder.py`) provides reusable graph construction.
- **Workflow** (`app/graph/workflow.py`) assembles the application.

Dependency direction:

```text
app/graph/workflow.py  ->  app/graph/builder.py  ->  LangGraph
```

The builder never imports the workflow, nodes, agents or business rules.

## Public Graph API

```python
from app.graph import (
    createGraph,
    addNode,
    addEdge,
    addConditionalEdge,
    compileGraph,
    validateGraph,
    START,
    END,
)
```

These functions are re-exported from `app.graph` and are the *only* public
graph API. There is exactly one authoritative implementation in
`app/graph/builder.py` — do not create duplicate graph helpers elsewhere.

## How to Create a Graph

```python
from typing import TypedDict
from app.graph import createGraph, addNode, addEdge, compileGraph, START, END


class MyState(TypedDict, total=False):
    value: int


async def my_node(state: MyState) -> dict:
    return {"value": state.get("value", 0) + 1}


graph = createGraph(MyState, name="my_graph")

addNode(graph, "my_node", my_node)          # sync or async callable
addEdge(graph, START, "my_node")
addEdge(graph, "my_node", END)

compiled = compileGraph(graph)
result = await compiled.ainvoke({"value": 0})
```

`createGraph` returns a fresh, independent `GraphContext`. It never mutates a
global graph, so multiple graphs can coexist and every test can build its own.

## How to Add a Node

```python
addNode(graph, "some_node", some_node_function, metadata={"team": "sre"})
```

Validation performed by `addNode`:

- node name must be a non-empty string
- duplicate node names raise `DuplicateNodeError`
- non-callables raise `InvalidNodeError`

Async nodes are fully supported (the triage workflow runs with `ainvoke`).

## How to Add an Edge

```python
addEdge(graph, "node_a", "node_b")   # normal directed edge
addEdge(graph, START, "node_a")      # from entry point
addEdge(graph, "node_b", END)        # to exit point
```

Edges referencing unknown nodes raise `InvalidEdgeError`.

## How to Add a Conditional Edge

```python
def route(state: MyState) -> str:
    return "end" if state["value"] >= 10 else "node_a"

addConditionalEdge(
    graph,
    source="node_b",
    router=route,
    path_map={"node_a": "node_a", "end": END},
)
```

The router decides the route; the builder connects it to the graph. Business
routing rules belong in `app/graph/router.py`, never in the builder.

## How to Compile a Graph

```python
compiled = compileGraph(graph)
compiled = compileGraph(graph, checkpointer=checkpointer)  # for interrupts
```

Compilation is centralized. The checkpointer comes from the context unless an
explicit one is supplied.

## Integrating an Independent Agent

An independent feature (e.g. `app/agents/database_analysis/` +
`app/graph/nodes/database_analysis.py`) contributes a capability through the
public API:

```python
from app.graph import addNode, addEdge

addNode(graph, "database_analysis", database_analysis_node)
addEdge(graph, "some_node", "database_analysis")
```

The feature owns its capability. The workflow owns composition. The feature
never needs to understand LangGraph internals or modify `builder.py`.

## Application-Specific Workflow

Application assembly belongs in `app/graph/workflow.py`. The v2 flow:

```text
ingestion -> classification -> investigation -> investigation_summary
-> rca_report -> approval -> verification -> notification
```

`verification` routes resolved incidents to `notification` and unresolved ones
back to `investigation` (re-investigation loop). Build/compile helpers:

```python
from app.graph import build_workflow, compile_workflow, create_checkpointer

compiled = compile_workflow(checkpointer=create_checkpointer())
```

## Human-in-the-Loop (Approval)

The `approval` node pauses the graph via a LangGraph interrupt and resumes with
a human decision. Framework control-flow exceptions are never swallowed by the
builder or node wrappers.

```python
from langgraph.types import Command

first = await compiled.ainvoke({"incident": payload}, config)
assert "__interrupt__" in first

resumed = await compiled.ainvoke(
    Command(resume={"approved": True}), config
)
```

## Testing

```bash
uv run pytest
```

Test layout:

- `tests/test_builder.py` — generic builder behavior using arbitrary nodes
- `tests/test_workflow.py` — v2 assembly, nodes, edges, routing, execution
- `tests/test_approval.py` — interrupt/resume integration
- `tests/test_public_api.py` — import surface / exports

Every test constructs its own graph; there is no shared mutable graph state.
