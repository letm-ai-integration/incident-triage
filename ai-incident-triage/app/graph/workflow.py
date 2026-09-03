# LangGraph workflow assembly.
#
# v2 flow:
#   ingestion -> classification (category + severity)
#     -> investigation (parallel sub-agents)
#     -> investigation_summary -> rca_report -> approval
#     -> verification (resolved -> notification; unresolved -> loop to investigation)
#     -> notification
#
# The classification/approval/verification stages branch through the pure
# routing functions in router.py. All node/edge registration goes through
# builder.py's public API.
from typing import Any

from app.graph.builder import (
    END,
    START,
    add_conditional_edge,
    add_edge,
    add_node,
    compile_graph,
    create_graph,
)
from app.graph.events import RunEventBus
from app.graph.nodes import (
    approval_node,
    classification_node,
    ingestion_node,
    investigation_node,
    investigation_summary_node,
    notification_node,
    rca_report_node,
    verification_node,
)
from app.graph.router import (
    route_after_approval,
    route_after_classification,
    route_after_verification,
)
from app.graph.state import IncidentState
from app.telemetry.tracing import get_langfuse_callback_handlers


def build_triage_graph():
    """Assemble (but do not compile) the production incident-triage graph."""
    graph = create_graph(state_schema=IncidentState)

    add_node(graph, "ingestion", ingestion_node)
    add_node(graph, "classification", classification_node)
    add_node(graph, "investigation", investigation_node)
    add_node(graph, "investigation_summary", investigation_summary_node)
    add_node(graph, "rca_report", rca_report_node)
    add_node(graph, "approval", approval_node)
    add_node(graph, "verification", verification_node)
    add_node(graph, "notification", notification_node)

    add_edge(graph, START, "ingestion")
    add_edge(graph, "ingestion", "classification")

    add_conditional_edge(
        graph,
        "classification",
        route_after_classification,
        {
            "full_investigation": "investigation",
            "auto_resolve": "notification",
        },
    )

    add_edge(graph, "investigation", "investigation_summary")
    add_edge(graph, "investigation_summary", "rca_report")
    add_edge(graph, "rca_report", "approval")

    add_conditional_edge(
        graph,
        "approval",
        route_after_approval,
        {
            "approved": "verification",
            "rejected": "notification",
        },
    )

    add_conditional_edge(
        graph,
        "verification",
        route_after_verification,
        {
            "reinvestigate": "investigation",
            "completed": "notification",
        },
    )

    add_edge(graph, "notification", END)
    return graph


def compile_triage_graph():
    """Compile the production triage graph into an executable graph."""
    return compile_graph(build_triage_graph())


triage_graph = compile_triage_graph()


def stream_triage_graph(
    raw_input: dict[str, Any],
    deps: dict[str, Any],
    run_id: str | None = None,
) -> tuple[Any, "RunEventBus"]:
    """Stream the triage graph execution, emitting live per-node ``NodeEvent``\\ s.

    Returns ``(generator, bus)`` where:

    * ``generator`` lazily yields one ``NodeEvent`` per node transition
      (``running`` then ``success``/``error``) as the graph executes.
    * ``bus`` is the run-scoped :class:`RunEventBus` carrying the full event
      log, the ``{node_name: latest_event}`` map, the captured
      ``final_state``, and fleet ``completed``/``error`` flags.

    The event bus is threaded through ``config["configurable"]["event_bus"]`` so
    the builder's node wrapper can emit events without touching any node code,
    and the tracing handler (``config["configurable"]["trace_handler"]``) wires
    LLM/tool calls into each node's ``agent_trace``.
    """
    if run_id is None:
        import uuid

        run_id = str(uuid.uuid4())

    bus = RunEventBus(run_id)

    from app.graph.tracing import TracingCallbackHandler

    callback_handler = TracingCallbackHandler(run_id, bus)
    # Expose the handler on the bus so the UI can splice *live* (in-flight)
    # trace entries into the detail panel while a node is still executing.
    bus.trace_handler = callback_handler

    config = {
        "configurable": {
            "deps": deps,
            "run_id": run_id,
            "event_bus": bus,
            "trace_handler": callback_handler,
        },
        "recursion_limit": 50,
        "callbacks": [callback_handler, *get_langfuse_callback_handlers()],
    }

    def _generator():
        from app.graph.tracing import clear_run_ctx, set_run_ctx

        cursor = 0
        set_run_ctx(run_id, bus, callback_handler)
        try:
            # stream_mode=["custom", "values"]:
            #  - the node wrapper (builder.py) pushes a "custom" event the moment a
            #    node (or nested sub-agent) *starts*, so "running" reaches the UI
            #    immediately instead of being batched with the node's completion.
            #  - "values" emits the cumulative state after each node finishes,
            #    which we use for the terminal final_state (no second invoke).
            for mode, payload in triage_graph.stream(
                {"raw_input": raw_input},
                config,
                stream_mode=["custom", "values"],
            ):
                if mode == "values":
                    bus.final_state = payload
                # A nested sub-agent changed status (written by the trace helpers
                # right after it updates bus.subagent_states). Surface it so the
                # UI re-renders the graph canvas / child pills live.
                if isinstance(payload, dict) and payload.get("kind") == "subagent":
                    yield payload
                    continue
                # Every node custom event is written right after its NodeEvent
                # lands on the bus, so drain-and-yield gives the UI fresh events.
                for event in bus.drain_since(cursor):
                    yield event
                cursor = len(bus.events)
        except Exception as exc:
            bus.error = str(exc)
            # Flush any events emitted before the failure so the UI can mark the
            # failing node red, then propagate the error for the caller to show.
            for event in bus.drain_since(cursor):
                yield event
            raise
        finally:
            bus.completed = True
            clear_run_ctx()

    return _generator(), bus
