# Canonical event contract for the incident-triage pipeline.
# Every node emits NodeEvents (or a subset) so the UI can render live per-node
# status, input/output snapshots, and agent_trace (LLM/tool call details).

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal


@dataclass
class NodeEvent:
    run_id: str
    node_name: str
    status: Literal["pending", "running", "success", "error"]
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: float | None = None
    input_snapshot: dict[str, Any] | None = None
    output_snapshot: dict[str, Any] | None = None
    agent_trace: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def utcnow() -> datetime:
    """Timezone-aware UTC *now* (replaces the deprecated ``datetime.utcnow``)."""
    return datetime.now(UTC)


def snapshot(value: Any) -> Any:
    """Recursively convert Pydantic models, dataclasses, enums, datetimes and
    other arbitrary objects into plain JSON-serialisable values.

    This lets the UI render input/output snapshots without importing domain
    models. Anything it cannot serialise cleanly falls back to ``repr``.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        try:
            return snapshot(value.model_dump())
        except Exception:  # noqa: BLE001 -- fall back to repr on any serialisation error
            return repr(value)
    if isinstance(value, (list, tuple, set)):
        return [snapshot(v) for v in value]
    if isinstance(value, dict):
        return {str(k): snapshot(v) for k, v in value.items()}
    if hasattr(value, "value") and hasattr(type(value), "__members__"):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {f: snapshot(getattr(value, f)) for f in value.__dataclass_fields__}
    return repr(value)


def make_snapshot(value: Any) -> dict[str, Any]:
    """Wrap :func:`snapshot` for a top-level state dict or node update dict."""
    if isinstance(value, dict):
        return {str(k): snapshot(v) for k, v in value.items()}
    return {"value": snapshot(value)}


def duration_ms(started: datetime | None, ended: datetime | None) -> float | None:
    """Elapsed milliseconds between two aware datetimes, or ``None``."""
    if started is None or ended is None:
        return None
    try:
        return round((ended - started).total_seconds() * 1000.0, 3)
    except TypeError:
        return None


class RunEventBus:
    """A run-scoped, in-memory sink for :class:`NodeEvent`\\ s.

    The Streamlit process (or CLI) creates one bus per run, passes it into the
    graph invocation via ``config["configurable"]["event_bus"]``, and drains it
    after each streamed step to render live, per-node updates.

    It maintains two views:

    * ``events`` / :meth:`drain_since` -- an append-only chronological log.
    * ``node_states`` -- a ``{node_name: latest_event}`` mapping used to colour
      the graph canvas and to collapse the timeline into one row per node.

    ``final_state`` is captured from the graph's ``values`` stream so the caller
    gets the terminal state for the "Final Result" panel without a second
    ``invoke``.
    """

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.events: list[NodeEvent] = []
        self.node_states: dict[str, NodeEvent] = {}
        # Live status of a node's fan-out sub-agent calls, keyed by parent node
        # then sub-agent name. Lets the graph canvas colour child pills live.
        self.subagent_states: dict[str, dict[str, str]] = {}
        self.final_state: dict[str, Any] | None = None
        self.completed: bool = False
        self.error: str | None = None

    def set_subagent_status(self, parent: str, name: str, status: str) -> None:
        """Record the live status of a fan-out sub-agent call under its parent."""
        self.subagent_states.setdefault(parent, {})[name] = status

    def emit(self, event: NodeEvent) -> None:
        """Append ``event`` to the log and record it as the latest for its node."""
        self.events.append(event)
        self.node_states[event.node_name] = event

    def drain_since(self, index: int) -> list[NodeEvent]:
        """Return events emitted since ``index`` (exclusive), in order.

        The caller tracks ``len(bus.events)`` as its own cursor.
        """
        index = max(index, 0)
        return self.events[index:]

    def last_event(self, node_name: str) -> NodeEvent | None:
        """The most recent event for ``node_name``, or ``None``."""
        return self.node_states.get(node_name)

    def node_order(self) -> list[str]:
        """Node names in first-execution (chronological) order."""
        seen: list[str] = []
        for event in self.events:
            if event.node_name not in seen:
                seen.append(event.node_name)
        return seen

    def merged_event(self, node_name: str) -> NodeEvent | None:
        """A single event per node that fuses the ``running`` event's input
        snapshot with the terminal event's output/trace/timing.

        This is what the timeline and detail panel render so there is exactly
        one row (and one detail view) per node even though a node may emit both
        a ``running`` and a ``success``/``error`` event.
        """
        running: NodeEvent | None = None
        terminal: NodeEvent | None = None
        for event in self.events:
            if event.node_name != node_name:
                continue
            if event.status == "running":
                running = event
            elif event.status in ("success", "error"):
                terminal = event
        base = terminal or running
        if base is None:
            return None
        return NodeEvent(
            run_id=base.run_id,
            node_name=node_name,
            status=base.status,
            started_at=(terminal.started_at if terminal else running.started_at),
            ended_at=(terminal.ended_at if terminal else running.ended_at),
            duration_ms=(terminal.duration_ms if terminal else running.duration_ms),
            input_snapshot=(running.input_snapshot if running else terminal.input_snapshot),
            output_snapshot=terminal.output_snapshot if terminal else None,
            agent_trace=terminal.agent_trace if terminal else (running.agent_trace or []),
            error=terminal.error if terminal else running.error,
        )
