# Task Brief: Instrument the Incident Triage Graph and Rebuild the Streamlit UI for Live, Per-Node Visibility

## 0. Context You Are Working With

This repo implements an **Incident Triage** pipeline built on **LangGraph**, exposed through a **Streamlit** UI. The current UI (see attached screenshots) is a static input form: Run options (Auto-approve, Use LLM-backed agents), a Guided Form / JSON toggle, incident fields (Title, Environment, Service, Priority hint, Source, Tags, Description, Log lines, Advanced JSON), and a single "Run Triage" button. Once triggered, the run is a black box — the user sees nothing until (presumably) a final result appears. There is no visibility into:

- which node/agent is currently executing
- what each node received as input and produced as output
- how long each step took, or whether it errored
- the shape of the graph itself (nodes, edges, conditional branches)
- intermediate agent reasoning/tool calls, when "Use LLM-backed agents" is on

Your job has two phases: **(1) audit and instrument** the `agents/` and `graph/` folders so every node emits structured, streamable events, and **(2) redesign the Streamlit UI** to consume those events live and render a genuinely informative, real-time view of the run — including the graph topology itself.

Do not guess at file names or node names below — they are placeholders. Your first action must be to read the actual code and replace every assumption with what you find.

---

## Phase 1 — Audit (do this before writing any code)

1. **Enumerate the graph.** Open every file in `graph/`. Identify:
   - The `StateGraph` (or `Graph`) definition — nodes, edges, conditional edges, entry point, `START`/`END`.
   - The shared state schema (`TypedDict`/`Pydantic` model) — what fields exist, which nodes read/write which fields.
   - Whether the graph is compiled once at import time or per-request, and whether checkpointing (`MemorySaver`, `SqliteSaver`, etc.) is already configured.
2. **Enumerate the agents.** Open every file in `agents/`. For each node/agent function, identify:
   - Is it a plain deterministic function, or does it call an LLM? If LLM-backed, which client/model, and does it use tools?
   - Its exact input slice of state and output slice of state.
   - Existing logging, if any (`print`, `logging`, `structlog`) — note format and whether it's reusable.
3. **Enumerate the current Streamlit entrypoint.** Find the file that renders the screenshots (likely `app.py`, `ui/streamlit_app.py`, or similar). Identify:
   - How "Run Triage" currently invokes the graph — `graph.invoke(...)` vs `graph.stream(...)` vs `graph.astream(...)`.
   - How the result is currently rendered (or not) after invocation.
   - Existing `st.session_state` usage, layout structure, and any custom CSS/theme already applied (the screenshots show a dark theme with a red/coral accent — preserve this).
4. **Produce a short written summary** (as a code comment block or a `NOTES.md`) of the actual graph topology (node list + edges) and the actual state schema before proceeding to Phase 2. This is the ground truth the UI will be built against — do not invent nodes that don't exist.

---

## Phase 2 — Instrument `agents/` and `graph/` for Observability

The core problem is that LangGraph's `invoke()` returns only a final state. To get live, per-node visibility you need **streaming + structured events**, not just streaming tokens.

### 2.1 Define a single event contract

Create one canonical event shape all nodes emit through, e.g. in `graph/events.py`:

```python
from dataclasses import dataclass, field
from typing import Any, Literal
from datetime import datetime

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
    agent_trace: list[dict[str, Any]] = field(default_factory=list)  # LLM calls, tool calls, reasoning
    error: str | None = None
```

`agent_trace` entries should capture, per LLM/tool call inside a node: `{"type": "llm_call"|"tool_call", "name": ..., "input": ..., "output": ..., "latency_ms": ...}`. This is what will let the UI show *what the agent was thinking/doing*, not just the node's final output.

### 2.2 Use LangGraph's native streaming, don't hand-roll it

Prefer `graph.stream(input, stream_mode=["updates", "custom"])` (or `astream_events` if you need token-level LLM streaming inside a node) over wrapping every node function manually. Concretely:

- `stream_mode="updates"` gives you a dict keyed by node name each time a node finishes — use this to build `NodeEvent(status="success", output_snapshot=...)` for free, without touching agent code.
- For **"running" (in-progress) status** and **agent_trace** detail, use LangGraph's `get_stream_writer()` inside each node (or a custom `BaseCallbackHandler`) to push intermediate events — e.g. "node X started", "node X called tool Y" — as they happen, not just on completion.
- If any node already calls an LLM client directly, attach a callback handler (`on_llm_start`, `on_llm_end`, `on_tool_start`, `on_tool_end`) rather than manually logging inside each agent function — this keeps agent code clean and centralizes tracing in one place (`graph/tracing.py`).

### 2.3 Wire a run-scoped event sink

Add a lightweight in-memory `EventBus` (a `queue.Queue` or a list in a thread-safe container) scoped to `run_id`, so the Streamlit process can drain it while the graph executes:

```python
class RunEventBus:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.events: list[NodeEvent] = []
    def emit(self, event: NodeEvent): ...
    def drain_since(self, index: int) -> list[NodeEvent]: ...
```

Pass this bus into the graph invocation (e.g. via `config={"configurable": {"event_bus": bus}}`) so nodes and the callback handler can push to it without global state.

### 2.4 Expose the graph topology programmatically

Do not hardcode the diagram in the UI. Use LangGraph's introspection so the UI diagram always matches the real graph:

```python
graph.get_graph().draw_mermaid()   # or .draw_mermaid_png() / .to_json()
```

Expose a small helper `graph/introspect.py::get_graph_topology()` returning `{"nodes": [...], "edges": [...], "conditional_edges": [...]}` for the UI to render and to map event `node_name`s onto.

### 2.5 Preserve determinism for non-LLM nodes

For nodes that are plain Python (e.g. tag normalization, priority auto-detect), still emit `NodeEvent`s (status/timing/input/output) even though there's no `agent_trace` — the UI should treat "deterministic step" and "agent step" as the same event type with an optional trace, not as two different systems.

---

## Phase 3 — Redesign the Streamlit UI

### 3.1 Design goals

- **Live**, not "wait then show" — the user watches the run happen node by node.
- **Graph-aware** — the topology from Phase 2.4 is always visible, with nodes visually changing state as the run progresses.
- **Per-node drill-down** — every node's input, output, timing, and agent trace is individually inspectable, not buried in one giant log.
- **Never lose the existing left-hand Run Options panel** — extend it, don't replace it.
- Keep the existing dark theme / coral accent color for visual continuity.

### 3.2 Proposed architecture: three-zone layout

Replace the current single-column form-then-nothing layout with a **persistent three-zone layout** that appears once "Run Triage" is clicked (the input form remains for editing/re-running):

```
┌─────────────┬───────────────────────────────┬─────────────────────┐
│  Run Options│         GRAPH CANVAS           │   ACTIVE NODE       │
│  (existing) │  live topology, node = pill,   │   DETAIL PANEL      │
│  + Run      │  color-coded by status,        │   (selected node's  │
│    History  │  animated edge on active path  │   input/output/     │
│             │                                 │   agent_trace/      │
│             ├───────────────────────────────┤   timing)            │
│             │      EXECUTION TIMELINE        │                     │
│             │  vertical stepper, one row per  │                     │
│             │  node, expandable, live-append  │                     │
└─────────────┴───────────────────────────────┴─────────────────────┘
                    ▼ (after run completes)
┌─────────────────────────────────────────────────────────────────┐
│  FINAL RESULT — triage classification, severity, summary,        │
│  recommended action, plus a "Raw JSON" expander                  │
└─────────────────────────────────────────────────────────────────┘
```

**Why this shape, specifically:**

- The **graph canvas** answers "where are we in the pipeline right now" at a glance — this is the thing a text log can never give you. Render it with `streamlit-agraph` (preferred, since it supports live node styling) or `st.graphviz_chart` driven by the topology from 2.4, re-rendered each poll with node fill color mapped from status: `gray` = pending, `amber pulsing` = running, `green` = success, `red` = error. Edges the run has actually traversed get highlighted; untraversed edges stay dim — this alone communicates conditional branching (e.g. "escalate" vs "auto-resolve" paths) far better than a log.
- The **execution timeline** is the append-only, chronological complement to the graph — good for scrollback and for seeing exact sequencing/duration, especially with parallel branches. Each row: node name, status icon, duration badge, one-line output preview; click/expand to populate the detail panel.
- The **detail panel** is where the "agent output" the user asked for actually lives in full: raw input state slice, raw output state slice, and — critically — the `agent_trace` rendered as a mini sub-timeline of LLM/tool calls (prompt in, completion out, tool name + args + result), collapsible per call. This is what makes LLM-backed nodes legible instead of a black box.
- **Run History** in the left rail (new) lets the user flip between past runs without losing the form — small addition, high value, minimal complexity.

### 3.3 Making it actually live in Streamlit

Streamlit has no native push channel, so implement live updates with one of these two patterns — pick based on what's simplest given your deployment:

**Pattern A — synchronous drain loop (simplest, recommended first):**
Run the graph in the *same* script execution as the button click, in a loop that steps the LangGraph stream and, after each event, updates pre-created placeholders (`st.empty()` containers for the graph canvas and a container you `.append`-render into for the timeline) — no `st.rerun()` needed mid-loop, since you're writing directly into placeholders within one execution:

```python
graph_slot = st.empty()
timeline_slot = st.container()
for event in run_and_stream(graph, inputs, bus):
    update_node_status(event)
    graph_slot.plotly_chart(render_graph(topology, node_states), use_container_width=True)
    with timeline_slot:
        render_timeline_row(event)
```

**Pattern B — background thread + polling rerun (if the graph runs long / needs to survive reruns):**
Kick off graph execution in a background thread that emits into `RunEventBus`; the main script polls `bus.drain_since(...)` on a `st_autorefresh`-driven rerun cadence (e.g. every 500ms via `streamlit-autorefresh` or `st.fragment` with `run_every=`). Use `st.session_state` to persist the event log and current node states across reruns. Prefer `st.fragment(run_every="0.5s")` (Streamlit ≥1.33) scoped to just the graph+timeline zone so the Run Options form doesn't re-render/flicker.

Recommend **Pattern A** unless a single triage run is expected to take longer than ~10–15 seconds or the user needs to navigate away mid-run — it's dramatically simpler and avoids thread-safety issues with Streamlit's execution model.

### 3.4 Component/library choices

- Graph rendering: `streamlit-agraph` (interactive, supports per-node color/label updates) or `graphviz` via `st.graphviz_chart` (simpler, static-per-frame but re-rendered each event — fully sufficient for Pattern A).
- Timeline rows: native `st.expander` per node, styled with `st.markdown` + inline HTML/CSS for the status pill to match the existing red/coral theme — no heavy component needed.
- Agent trace inside detail panel: nested `st.expander` per LLM/tool call, `st.code(..., language="json")` for prompts/tool args, syntax-highlighted.
- Keep everything themable via a small `ui/theme.py` with the existing dark palette constants so new components don't visually clash with the untouched Run Options panel.

### 3.5 What must NOT change

- The existing Guided Form / JSON toggle and all input fields — extend the page, don't replace the intake UX.
- Auto-approve / Use LLM-backed agents / LLM provider configured indicator — keep as-is in the left rail.

---

## Phase 4 — Implementation Checklist

1. [ ] Write `NOTES.md` summarizing actual graph topology + state schema (Phase 1 output).
2. [ ] Add `graph/events.py` (`NodeEvent`, `RunEventBus`).
3. [ ] Add `graph/tracing.py` (callback handler wiring LLM/tool calls into `agent_trace`).
4. [ ] Add `graph/introspect.py::get_graph_topology()`.
5. [ ] Modify graph compile/invoke call sites to use `stream_mode=["updates","custom"]` (or `astream_events`) and pass the event bus through `config`.
6. [ ] Add `ui/render_graph.py` (topology + live status → agraph/graphviz figure).
7. [ ] Add `ui/render_timeline.py` (event list → expandable stepper rows).
8. [ ] Add `ui/render_detail.py` (selected `NodeEvent` → input/output/agent_trace panel).
9. [ ] Restructure `app.py` layout into the three-zone grid (Section 3.2), wire Pattern A drain loop into the "Run Triage" handler.
10. [ ] Add Run History to the left rail using `st.session_state["runs"]`.
11. [ ] Add Final Result + Raw JSON section below the live zones, populated once the stream terminates.
12. [ ] Manual test: run one incident with `Use LLM-backed agents` ON and one with it OFF — confirm both render correctly (agent_trace present vs. empty is expected and both must degrade gracefully).
13. [ ] Manual test: force a node to raise, confirm it renders red on the graph, "error" in the timeline, and the exception surfaces in the detail panel instead of crashing the Streamlit app.

---

## Guiding Principle

Every element of the new UI should answer one of three questions the current UI cannot: **Where are we? What just happened at this specific node? What did the agent actually see and decide?** If a proposed UI element doesn't answer one of those three, cut it.
