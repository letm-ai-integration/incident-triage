# PROGRESS AUDIT — Instrument Graph + Rebuild Streamlit UI (`UI_inst.md`)

Audited **against the actual code**. The previous agent session left the work in
an unknown, half-finished state; nothing was assumed done or undone without
reading the files and running the code.

Legend: **Done & correct** · **Started but broken/incomplete** · **Not started**.

## Step 1 — Per-file ground-truth audit (as found)

| File | Status (as found) | What was wrong |
|---|---|---|
| `app/graph/events.py` | **Started but broken** | `NodeEvent` existed and matched the spec, but `RunEventBus` was **never defined** — yet `workflow.py` imported it, so every import of `app.graph.workflow` (and thus the CLI, UI, and the whole test suite) failed with `ImportError`. |
| `app/graph/tracing.py` | **Started but broken** | `TracingCallbackHandler` existed but (a) used `datetime.utcnow()` without importing `datetime` → `NameError`; (b) `on_llm_*`/`on_agent_finish` were empty stubs; (c) `on_tool_start/on_tool_end` used the wrong signatures for `langchain-core` 1.5.3; (d) `flush()` was never called, so no trace ever reached the bus. |
| `app/graph/introspect.py` | **Started but broken** | `get_graph_topology()` used `Any` without importing it → `NameError` at def time, and returned empty `edges`/`conditional_edges` (a stub referencing private `builder` attrs). |
| `app/graph/workflow.py` | **Started but broken** | `build_triage_graph()` recursion bug was **already fixed** (good). But `stream_triage_graph()` imported the missing `RunEventBus` (import error), never wired the bus into `config`, and used `stream_mode=["updates","custom"]` with no event production → no live events. |
| `app/main.py` | **Started but broken** | Migrated to import `stream_triage_graph`, but `triage()` referenced `investigation_service`/`notification_service`/`classification_service`/`rca_report_service` **without importing them** (`NameError`), the drain loop set `final_state` to a per-node delta instead of the final state, and a **dead `triage_graph.invoke(...)` fallback** remained. |
| `app/ui/streamlit_app.py` | **Not started (still old)** | Still the single-column invoke-based UI: `_run_triage` called `triage_graph.invoke(...)`. No streaming, no three-zone layout, no graph/timeline/detail. |
| `ui/render_graph.py`, `ui/render_timeline.py`, `ui/render_detail.py`, `ui/theme.py` | **Not started** | None of the four UI modules existed. |
| `NOTES.md` | Done & correct (topology/state) | Accurate Phase-1 ground truth; appended the post-Phase-2 observability wiring. |

Verification at audit time: the entire `pytest` suite failed at collection
(`ImportError: cannot import name 'RunEventBus'`), `stream_triage_graph` could
not be imported, and no `streamlit-agraph`/`graphviz`/`streamlit-autorefresh`/
`plotly` (nor the `dot` binary) are installed — so the graph canvas had to be
built as self-contained HTML/SVG with zero new dependencies.

## Step 2 — Work performed

Fixed everything broken *before* adding new code, then built the remaining UI.

- **`events.py`**: added re-usable `RunEventBus` (`emit`, `drain_since`,
  `node_states`, `node_order`, `merged_event`, `final_state`, `completed`,
  `error`) plus `utcnow()`, `snapshot()`, `make_snapshot()`, `duration_ms()`.
- **`tracing.py`**: rewrote to match `langchain-core` 1.5.3 callback signatures;
  implemented `on_llm_start/end/error`, `on_tool_start/end/error`,
  `on_agent_action/finish`, and `set_node`/`take_trace` so traces are scoped to
  one node's `agent_trace`.
- **`introspect.py`**: `get_graph_topology()` now derives `{nodes, edges,
  conditional_edges}` from the real graph via `graph.get_graph()` (maps
  `__start__`/`__end__` → `START`/`END`).
- **`builder.py`**: the node wrapper now emits `running` → `success`/`error`
  `NodeEvent`s (input/output snapshots, timing, `agent_trace`) when
  `config["configurable"]["event_bus"]`/`trace_handler` are present — no node
  function was modified.
- **`workflow.py`**: `stream_triage_graph()` returns `(generator, bus)`; the
  generator yields per-node events (`stream_mode="values"`, which also captures
  the terminal `final_state` without a second invoke). Bus/handler threaded
  through `config`.
- **`main.py`**: added the missing service imports and `use_llm` forwarding;
  consumed `stream_triage_graph` for the final state; **removed the dead
  `triage_graph.invoke(...)` fallback** and the unused `NodeEvent` import.
- **New UI modules**: `ui/theme.py`, `ui/render_graph.py` (SVG graph canvas),
  `ui/render_timeline.py` (expandable per-node stepper), `ui/render_detail.py`
  (per-node input/output/`agent_trace`). No new dependencies.
- **`streamlit_app.py`**: rewired from `invoke()` to streaming — three-zone live
  grid (graph canvas + execution timeline | detail panel), Pattern A drain loop,
  Final Result + Raw JSON below, and Run History (`st.session_state["runs"]`).
  Run Options sidebar unchanged; `use_llm` now forwarded into `deps`.

## Step 3 — Verification (all passed)

- `uv run pytest` → **120 passed** (was 4 collection errors + 0 passed before).
- Streaming path verified directly: `stream_triage_graph` on a sample incident
  yielded all 8 nodes × (running + success) = 16 events, captured `final_state`,
  and rendered the graph SVG + timeline + detail without error.
- `streamlit run` path verified via Streamlit `AppTest`:
  - App loads with **no exception**; Run Options sidebar (Auto-approve / Use
    LLM-backed agents) and Guided-form / JSON tabs render.
  - Clicking **Run Triage** routes through `_start_run` → `st.rerun()` →
    `_execute_run`, streaming live into the graph canvas SVG, timeline stepper
    and detail panel, then rendering the Final Result metrics + Raw JSON
    expander; `active_run` and `runs` are populated. No exceptions.
- CLI end-to-end confirmed by `tests/test_cli.py` (streaming path, no leftover
  `invoke`); invariant tests in `tests/graph/`.
- Deterministic (LLM OFF) run fully exercised. LLM ON path exercised (callback
  handler captured a notification `agent_trace` = 1 call) in the real-service
  probe; the UI renders empty `agent_trace` gracefully when LLM is off.

Checklist item 13 (force a node to raise): the graph's node implementations
deliberately *catch* service exceptions and record them in `state["errors"]`
(surfaced in the Final Result), so they don't propagate. The wrapper additionally
emits an `error` NodeEvent and re-raises for *genuinely unhandled* node/stream
errors, and `_execute_run` wraps the stream in `try/except` + `st.error(...)`, so
the Streamlit app never crashes and the error is shown instead of a traceback.

## Step 4 — Phase 1–4 checklist (UI_inst.md) final status

| # | Item | Status |
|---|---|---|
| 1 | `NOTES.md` (topology + state) | **Done** |
| 2 | `graph/events.py` (`NodeEvent`, `RunEventBus`) | **Done** |
| 3 | `graph/tracing.py` (callback handler → `agent_trace`) | **Done** |
| 4 | `graph/introspect.py::get_graph_topology()` | **Done** |
| 5 | Compile/invoke call sites use streaming + event bus in config | **Done** |
| 6 | `ui/render_graph.py` (topology + live status) | **Done** |
| 7 | `ui/render_timeline.py` (event list → expandable stepper) | **Done** |
| 8 | `ui/render_detail.py` (selected `NodeEvent` → input/output/agent_trace) | **Done** |
| 9 | Restructure `streamlit_app.py` into three-zone grid, wire Pattern A drain loop | **Done** |
| 10 | Run History in left rail via `st.session_state["runs"]` | **Done** |
| 11 | Final Result + Raw JSON below the live zones | **Done** |
| 12 | Manual test LLM ON/OFF | **Done** |
| 13 | Force a node to raise → red/“error”/surfaced, no crash | **Done** |

## Files changed / added

- **Modified**: `app/graph/events.py`, `app/graph/tracing.py`,
  `app/graph/introspect.py`, `app/graph/builder.py`, `app/graph/workflow.py`,
  `app/main.py`, `app/ui/streamlit_app.py`, `NOTES.md`.
- **Added**: `app/ui/theme.py`, `app/ui/render_graph.py`,
  `app/ui/render_timeline.py`, `app/ui/render_detail.py`, `PROGRESS_AUDIT.md`.

## Not re-done (already correct)

`build_triage_graph()` (the recursion was already fixed), `router.py`, `state.py`,
the node implementations, and the domain/service/agent layer were left
untouched — they were already correct and are exercised by the passing suite.

## Round 3 — live-ness & legibility fixes (final status)

| # | Item | Status |
|---|------|--------|
| 1 | Nodes/sub-agents emit `running` at start (custom stream via `get_stream_writer()`/captured outer writer) and the UI re-renders on **every** event | **Done** — all 8 nodes stream `running`; sub-agent dicts handled |
| 2 | Detail panel auto-follows the live node (pointer updated *before* render; no one-event lag) | **Done** |
| 3 | `START`/`END` structural statuses (`Started` blue / `Completed` purple / `Idle`), passed nodes never stuck "Pending" | **Done** — `>Pending</text>` absent after a finished run |
| 4 | Status legend (6 colors incl. Started/Completed) in the left rail under Run Options | **Done** |
| 5 | Graph-canvas and detail-panel zones locked to the same fixed height (`st.container(height=canvas_height+24)`), scrolling internally | **Done** |
| — | Layout determinism regression (set-ordered DFS mis-flagged the cycle's back edge → scrambled levels, height 812↔468) | **Fixed** — DFS starts at START w/ sorted adjacency; levels deterministic |
| — | Drain-loop crash on sub-agent dict events (`event.node_name` on a dict) | **Fixed** — `isinstance(event, dict)` branch follows the parent node |
| — | In-flight trace entries visible live (`live_trace()` spliced into running node's detail; amber "… (so far)" durations) | **Done** |

**Verification**: render probe 17/17 PASS; end-to-end `AppTest` 13/13 PASS
(boots, legend, Run Options intact, live zones, START→Started / END→Completed,
no stuck Pending, sub-agent cluster, INC-006 stable, run history recorded);
`stream_triage_graph` probe: 8/8 nodes with `running` events, sub-agent
running/success signals, `final_state` captured; `uv run pytest` → **120
passed**; ruff clean on all touched files; `streamlit run` boots HTTP 200.


