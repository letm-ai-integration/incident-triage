# Callback handler that wires LLM/tool calls inside nodes into ``agent_trace``
# on the shared ``RunEventBus``. The node wrapper (see ``builder.py``) calls
# ``set_node`` before a node executes and ``take_trace`` after, so the trace is
# scoped to exactly one node and then attached to that node's ``NodeEvent``.
#
# Matches the ``langchain-core`` 1.5.x ``BaseCallbackHandler`` signatures so the
# handler is invoked by LangChain/LangGraph without adapter hacks.

from __future__ import annotations

import contextvars
import json
import logging
from datetime import UTC, datetime
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from app.graph.events import snapshot

logger = logging.getLogger(__name__)

# The node wrapper sets the *currently executing* handler here so any deeply
# nested sync/async sub-agent call can append its own ``subagent`` trace entry
# to the owning node's ``agent_trace`` (and push a live status into the bus).
# Holding it in a contextvar (rather than a module global) lets it propagate
# into the ``asyncio.run``'d investigation subgraph correctly.
_current_tracer: contextvars.ContextVar[TracingCallbackHandler | None] = (
    contextvars.ContextVar("current_tracer", default=None)
)

# Run-scoped (run_id, bus, handler) that the Streamlit/CLI process sets for the
# duration of a run. The builder's node wrapper falls back to this when LangGraph
# does not thread ``config["configurable"]["event_bus"]`` to the *entry* node
# (which is exactly why ``ingestion`` was being dropped and stuck on "Pending").
_run_ctx: contextvars.ContextVar[tuple[str, Any, Any] | None] = (
    contextvars.ContextVar("run_ctx", default=None)
)


def set_run_ctx(run_id: str, bus: Any, handler: Any) -> None:
    _run_ctx.set((run_id, bus, handler))


def clear_run_ctx() -> None:
    _run_ctx.set(None)


def current_run_ctx() -> tuple[str, Any, Any] | None:
    return _run_ctx.get()


# The *outer* graph's live stream writer (per top-level node). Nested subgraph
# invocations resolve a no-op writer of their own, so the trace helpers must
# write through this captured writer instead of calling ``get_stream_writer()``
# inside a nested invoke, or the outer stream never sees sub-agent events.
_outer_writer: contextvars.ContextVar[Any | None] = (
    contextvars.ContextVar("outer_writer", default=None)
)


def set_outer_writer(writer: Any | None) -> None:
    _outer_writer.set(writer)


def clear_outer_writer() -> None:
    _outer_writer.set(None)


# True while a nested LangGraph subgraph (e.g. the investigation phase graph) is
# being invoked. Its nodes share the run context, so without this flag they
# would emit bogus top-level ``NodeEvent``\\ s; we only want *their* ``subagent``
# trace entries, which the trace helpers record directly.
_suppress_node_events: contextvars.ContextVar[bool] = (
    contextvars.ContextVar("suppress_node_events", default=False)
)


def suppress_node_events() -> None:
    _suppress_node_events.set(True)


def unsuppress_node_events() -> None:
    _suppress_node_events.set(False)


def node_events_suppressed() -> bool:
    return bool(_suppress_node_events.get())


def emit_custom(payload: Any) -> None:
    """Push ``payload`` to LangGraph's live ``custom`` stream channel.

    This is what makes a ``running`` event reach the UI the instant a node (or a
    nested sub-agent) starts, instead of only once it completes. It is a no-op
    when the graph is not being streamed (e.g. ``invoke`` in tests).

    Prefers the *outer* graph's captured writer so that calls made inside nested
    subgraph invocations (whose own writer is a silent no-op) still surface live
    on the top-level stream.
    """
    writer = _outer_writer.get()
    if writer is None:
        try:
            from langgraph.config import get_stream_writer

            writer = get_stream_writer()
        except Exception:  # noqa: BLE001 -- no live stream (invoke/tests)
            return
    try:
        writer(payload)
    except Exception:  # noqa: BLE001, S110 -- never fail a node because the stream dropped it
        pass


def _ms(started: datetime | None, ended: datetime | None) -> float | None:
    if started is None or ended is None:
        return None
    return round((ended - started).total_seconds() * 1000.0, 3)


def trace_sync(name: str, input_val: Any, fn, *args: Any, **kwargs: Any) -> Any:
    """Run ``fn`` recording a ``subagent`` trace entry on the current node.

    Used by (synchronous) sub-agents so the UI can show each fan-out call as an
    independently-coloured child, even when no LangChain LLM callback fires.
    """
    handler = _current_tracer.get()
    started = datetime.now(UTC)
    parent = handler._node_name if handler else None
    if handler is not None:
        entry: dict[str, Any] = {
            "type": "subagent", "name": name, "input": snapshot(input_val),
            "started_at": started,
        }
        handler._trace.append(entry)
        if parent:
            handler.bus.set_subagent_status(parent, name, "running")
    if parent:
        emit_custom({"kind": "subagent", "parent": parent, "name": name, "status": "running"})
    try:
        result = fn(*args, **kwargs)
    except Exception as exc:
        if handler is not None:
            entry["status"] = "error"
            entry["output"] = str(exc)
            entry["ended_at"] = datetime.now(UTC)
            entry["duration_ms"] = _ms(started, entry["ended_at"])
            if parent:
                handler.bus.set_subagent_status(parent, name, "error")
        if parent:
            emit_custom({"kind": "subagent", "parent": parent, "name": name, "status": "error"})
        raise
    if handler is not None:
        entry["status"] = "success"
        entry["output"] = snapshot(result)
        entry["ended_at"] = datetime.now(UTC)
        entry["duration_ms"] = _ms(started, entry["ended_at"])
        if parent:
            handler.bus.set_subagent_status(parent, name, "success")
    if parent:
        emit_custom({"kind": "subagent", "parent": parent, "name": name, "status": "success"})
    return result


async def trace_async(name: str, input_val: Any, coro) -> Any:
    """``await`` ``coro`` recording a ``subagent`` trace entry on the current node."""
    handler = _current_tracer.get()
    started = datetime.now(UTC)
    parent = handler._node_name if handler else None
    entry: dict[str, Any] = {}
    if handler is not None:
        entry = {
            "type": "subagent", "name": name, "input": snapshot(input_val),
            "started_at": started,
        }
        handler._trace.append(entry)
        if parent:
            handler.bus.set_subagent_status(parent, name, "running")
    if parent:
        emit_custom({"kind": "subagent", "parent": parent, "name": name, "status": "running"})
    try:
        result = await coro
    except Exception as exc:
        if handler is not None:
            entry["status"] = "error"
            entry["output"] = str(exc)
            entry["ended_at"] = datetime.now(UTC)
            entry["duration_ms"] = _ms(started, entry["ended_at"])
            if parent:
                handler.bus.set_subagent_status(parent, name, "error")
        if parent:
            emit_custom({"kind": "subagent", "parent": parent, "name": name, "status": "error"})
        raise
    if handler is not None:
        entry["status"] = "success"
        entry["output"] = snapshot(result)
        entry["ended_at"] = datetime.now(UTC)
        entry["duration_ms"] = _ms(started, entry["ended_at"])
        if parent:
            handler.bus.set_subagent_status(parent, name, "success")
    if parent:
        emit_custom({"kind": "subagent", "parent": parent, "name": name, "status": "success"})
    return result


def _serialize_tool_input(input_str: str, inputs: Any) -> Any:
    """Best-effort parse of a tool input that may come as a JSON string."""
    if inputs:
        return snapshot(inputs)
    if not input_str:
        return {}
    try:
        return json.loads(input_str)
    except (json.JSONDecodeError, TypeError):
        return {"raw": input_str}


class TracingCallbackHandler(BaseCallbackHandler):
    """``LangChain`` callback handler that captures LLM/tool calls into
    ``agent_trace`` on a per-node ``NodeEvent`` pushed to the event bus.

    Usage:
        - Instantiate with ``bus`` (``RunEventBus``) and ``run_id``.
        - Pass ``callbacks=[handler]`` into the graph invocation config.
        - The builder's node wrapper calls ``handler.set_node(name)`` before the
          node runs and ``handler.take_trace()`` afterwards so the captured
          trace is attached to the correct node event.
    """

    def __init__(self, run_id: str, bus: Any) -> None:
        self.run_id = run_id
        self.bus = bus
        self._node_name: str | None = None
        self._trace: list[dict[str, Any]] = []

    def set_node(self, node_name: str | None) -> None:
        """Called by the node wrapper immediately before a node executes."""
        self._node_name = node_name
        self._trace = []
        # Make this handler the active tracer so nested sync/async sub-agents
        # (e.g. the investigation fan-out) can append their own trace entries.
        _current_tracer.set(self)

    def take_trace(self) -> list[dict[str, Any]]:
        """Return and clear the accumulated trace for the current node."""
        trace = list(self._trace)
        self._trace = []
        _current_tracer.set(None)
        return trace

    def live_trace(self) -> list[dict[str, Any]]:
        """The accumulated trace *without* clearing it.

        The UI splices this into a running node's detail view so in-flight
        sub-agent/LLM calls appear (with their own ``running`` status) the
        moment they start, not only once the node completes.
        """
        return list(self._trace)

    # -- LLM calls ---------------------------------------------------------
    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        self._trace.append(
            {
                "type": "llm_call",
                "name": (serialized or {}).get("name", "LLM"),
                "input": {"prompts": list(prompts)},
                "started_at": datetime.now(UTC),
            }
        )

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        text = ""
        try:
            text = getattr(response.generations[0][0], "text", "") or ""
        except (AttributeError, IndexError, TypeError):
            text = repr(response) if response is not None else ""
        self._attach_llm_output(status="success", output=text)

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        self._attach_llm_output(status="error", output=str(error))

    def _attach_llm_output(self, status: str, output: str) -> None:
        for record in reversed(self._trace):
            if record.get("type") == "llm_call" and "ended_at" not in record:
                record["status"] = status
                record["output"] = output
                record["ended_at"] = datetime.now(UTC)
                return
        self._trace.append(
            {"type": "llm_call", "status": status, "output": output, "ended_at": datetime.now(UTC)}
        )

    # -- Tool calls --------------------------------------------------------
    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        name = ""
        if isinstance(serialized, dict):
            name = serialized.get("name", "") or ""
        elif serialized is not None:
            name = getattr(serialized, "name", "") or ""
        self._trace.append(
            {
                "type": "tool_call",
                "name": name or "tool",
                "input": _serialize_tool_input(input_str, inputs),
                "started_at": datetime.now(UTC),
            }
        )

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        self._attach_tool_output(status="success", output=output)

    def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        self._attach_tool_output(status="error", output=str(error))

    def _attach_tool_output(self, status: str, output: Any) -> None:
        for record in reversed(self._trace):
            if record.get("type") == "tool_call" and "ended_at" not in record:
                record["status"] = status
                record["output"] = snapshot(output)
                record["ended_at"] = datetime.now(UTC)
                return
        self._trace.append(
            {
                "type": "tool_call",
                "status": status,
                "output": snapshot(output),
                "ended_at": datetime.now(UTC),
            }
        )

    # -- Agent steps (older, mostly superseded by tool/llm callbacks) ------
    def on_agent_action(self, action: Any, **kwargs: Any) -> None:
        tool_name = getattr(action, "tool", None) or (
            action.get("tool") if isinstance(action, dict) else None
        )
        tool_input = getattr(action, "tool_input", None) or (
            action.get("tool_input") if isinstance(action, dict) else None
        )
        self._trace.append(
            {
                "type": "agent_action",
                "name": tool_name or "agent",
                "input": snapshot(tool_input),
                "started_at": datetime.now(UTC),
            }
        )

    def on_agent_finish(self, finish: Any, **kwargs: Any) -> None:
        return_values = getattr(finish, "return_values", None) or (
            finish.get("return_values") if isinstance(finish, dict) else None
        )
        self._trace.append(
            {"type": "agent_finish", "output": snapshot(return_values), "ended_at": datetime.now(UTC)}
        )


__all__ = [
    "TracingCallbackHandler",
    "clear_outer_writer",
    "clear_run_ctx",
    "current_run_ctx",
    "emit_custom",
    "node_events_suppressed",
    "set_outer_writer",
    "set_run_ctx",
    "suppress_node_events",
    "trace_async",
    "trace_sync",
    "unsuppress_node_events",
]
