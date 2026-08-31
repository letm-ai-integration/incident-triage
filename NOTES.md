# NOTES — Graph Topology and State Schema (Ground Truth for UI Redesign)

## Graph Topology (from `app/graph/workflow.py`)

The triage pipeline is a single compiled LangGraph `StateGraph` with 8 stages and conditional branching. Entry and exit are `START` and `END`.

### Node list (8 nodes, in execution order):

| Node name | File | Backing |
|---|---|---|
| `ingestion` | `app/graph/nodes/ingestion.py` | Deterministic – builds `Incident` from raw input |
| `classification` | `app/graph/nodes/classification.py` | LLM-backed optional (via `classification_service` deps); rule-based fallback always available |
| `investigation` | `app/graph/nodes/investigation.py` | Always runs `investigation_service` (which delegates to the Investigation Orchestrator subgraph); deterministic fallbacks when no LLM |
| `investigation_summary` | `app/graph/nodes/investigation_summary.py` | Deterministic – aggregates evidence/hypothesis counts |
| `rca_report` | `app/graph/nodes/rca_report.py` | LLM-backed optional (via `rca_report_service` deps); rule-based fallback otherwise |
| `approval` | `app/graph/nodes/approval.py` | Deterministic fallback `_default_approve`; production policy injected via `approval_service` deps |
| `verification` | `app/graph/nodes/verification.py` | Deterministic fallback `_default_verify` |
| `notification` | `app/graph/nodes/notification.py` | Always runs `notification_service` (LLM draft + Resend delivery); simulated when no `RESEND_API_KEY` |

### Edge list (unconditional + conditional):

| Source | Target | Type | Router / path_map |
|---|---|---|---|
| `START` | `ingestion` | unconditional | — |
| `ingestion` | `classification` | unconditional | — |
| `classification` | `investigation` | conditional | `route_after_classification` → {"full_investigation": "investigation", "auto_resolve": "notification"} |
| `classification` | `notification` | conditional | via `route_after_classification` path_map (auto_resolve branch) |
| `investigation` | `investigation_summary` | unconditional | — |
| `investigation_summary` | `rca_report` | unconditional | — |
| `rca_report` | `approval` | unconditional | — |
| `approval` | `verification` | conditional | `route_after_approval` → {"approved": "verification", "rejected": "notification"} |
| `approval` | `notification` | conditional | via `route_after_approval` path_map (rejected branch) |
| `verification` | `investigation` | conditional | `route_after_verification` → {"reinvestigate": "investigation", "completed": "notification"} |
| `verification` | `notification` | conditional | via `route_after_verification` path_map (completed branch) |
| `notification` | `END` | unconditional | — |

### Conditional routing (router functions in `app/graph/router.py`):

- `route_after_classification(state)`: Returns `"full_investigation"` for P1/P2, unknown type, or low confidence; `"auto_resolve"` for P4.
- `route_after_approval(state)`: Returns `"rejected"` if approval is not approved, else `"approved"`.
- `route_after_verification(state)`: Returns `"reinvestigate"` if verification not resolved and retries remain; `"completed"` otherwise.

### Compilation:

- Graph is assembled once via `build_triage_graph()` (calls `create_graph`, `add_node`, `add_edge`, `add_conditional_edge`, then `compile_graph`).
- `triage_graph = compile_triage_graph()` at module level (import-time).
- No checkpointing (`MemorySaver`/etc.) is configured — each invocation is ephemeral.

---

## Shared State Schema (from `app/graph/state.py`)

`IncidentState` is a `TypedDict, total=False` — fields are added as the pipeline progresses. Key groupings:

### 1. Incident Input
- `incident_id: str`
- `incident: Incident` (Pydantic model)
- `raw_input: dict`
- `normalized_input: dict` (= `incident.model_dump()` after ingestion)

### 2. Classification
- `classification: ClassificationResult` (Pydantic – incident_type, priority, confidence, reasoning, etc.)
- `incident_type: IncidentType` (enum)
- `severity: Priority` (enum P1–P4)
- `classification_confidence: float`

### 3. Investigation
- `investigation_status: IncidentStatus` (NEW, TRIAGING, INVESTIGATING, RESOLVED, UNRESOLVED)
- `evidence: list[Evidence]`
- `hypotheses: list[Hypothesis]`
- Parallel sub-agent outputs: `log_analysis: Evidence`, `runbook_analysis: Evidence`, `kubernetes_analysis: Evidence`
- `runbook_name: str | None`, `runbook_solution: str | None`
- `retry_count: int`, `current_step: str`, `errors: list[str]`

### 4. Investigation Summary
- `investigation_summary: dict` (summary text, evidence_count, hypothesis_count, top_hypothesis_id, sources)

### 5. RCA & Report
- `root_cause: RootCauseAnalysis`
- `rca_confidence: float`
- `incident_report: IncidentReport` (full report with evidence, hypotheses, root_cause, recommended_actions, runbook_references, verification, approval, created_at)

### 6. Verification
- `expected_outcome: dict`
- `verification_result: VerificationResult` (is_resolved, resolution_evidence, needs_reinvestigation, reinvestigation_hints)
- `is_resolved: bool`

### 7. Workflow Control
- `retry_count: int`, `current_step: str`, `errors: list[str]`

### 8. Approval
- `approval: ApprovalDecision` (approved=True/False, reviewer, comments, timestamp)
- `approval_status: ApprovalStatus` (APPROVED, REJECTED)
- `notification_status: NotificationStatus` (NOTIFIED, FAILED)

---

## LLM-backed vs Deterministic Nodes

| Node | LLM-backed | Deterministic fallback |
|---|---|---|
| `ingestion` | No | `_default_ingest` (keyword parsing) |
| `classification` | Yes, via `classification_service` deps (opt-in `--use-llm`) | `_default_classify` (keyword matching on title/description) |
| `investigation` | Yes, via `investigation_service` → orchestrator subgraph (always injected) | Deterministic sub-agents (log_analysis, kubernetes, runbook) with keyword fallbacks |
| `investigation_summary` | No | `_default_investigation_summary` (counts + top hypothesis) |
| `rca_report` | Yes, via `rca_report_service` deps (opt-in `--use-llm`) | `_default_rca_report` (picks top hypothesis by confidence) |
| `approval` | No (policy service injected optionally) | `_default_approve` (auto-approve unless P1/P2 or low confidence) |
| `verification` | No | `_default_verify` (confidence threshold check) |
| `notification` | Yes, via `notification_service` → agent (LLM email draft + Resend) | `_default_notify` (marks status based on verification) |

---

## Current UI Invocation (from `app/ui/streamlit_app.py`)

- The UI calls `triage_graph.invoke({"raw_input": raw_input}, config={"configurable": {"deps": deps}, "recursion_limit": RECURSION_LIMIT})`.
- `invoke()` returns **only the final state dict** — no per-node visibility.
- No streaming is used; the run is a black box from the UI's perspective.
- `deps` includes: `auto_approve`, `investigation_service`, `notification_service`, and conditionally `classification_service` / `rca_report_service` when LLM is configured and opted in.

---

## Key Integration Points for UI Redesign

1. **Graph introspection**: `graph.get_graph()` gives the full topology (nodes, edges, conditional edges). The UI must use this, not hardcode the diagram.
2. **State fields**: Every node writes a known subset of `IncidentState`. The UI should map node names → state fields they produce/consume.
3. **Conditional branches**: `route_after_classification`, `route_after_approval`, `route_after_verification` dictate which edge was taken. The UI must surface which path was chosen (e.g., "auto-resolve" vs "full_investigation", "approved" vs "rejected", "reinvestigate" vs "completed").
4. **LLM opt-in**: Classification and RCA agents are only LLM-backed when `deps["classification_service"]` / `deps["rca_report_service"]` are present. The UI must reflect this (agent_trace empty vs. populated).
5. **Error handling**: Node errors are captured in `state["errors"]` and also propagated as exceptions. The UI must not crash on errors — show them in the detail panel.

---

## What the UI Currently Lacks (per UI_inst.md)

- No visibility into which node/agent is currently executing
- No input/output snapshots per node
- No timing or error info per step
- No graph topology visualization
- No agent trace (LLM/tool calls) per node
- Black-box execution — user sees nothing until the final result appears

---

## Observability / Streaming wiring (post-Phase-2, added)

The graph is now instrumented for live, per-node visibility. Key pieces:

- **`app/graph/events.py`** — `NodeEvent` (run_id, node_name, status, timing,
  input/output snapshots, `agent_trace`, error) + `RunEventBus` (run-scoped
  in-memory sink: `events` log, `node_states` latest-per-node map, `final_state`,
  `completed`/`error` flags). `snapshot()` converts domain models/enums to plain
  JSON for display. The node wrapper (~`builder.py`) emits a `running` event
  before a node executes and a `success`/`error` event after, so a node produces
  two events; the UI fuses them into one row per node.
- **`app/graph/tracing.py`** — `TracingCallbackHandler` wired through
  `config["callbacks"]`; `set_node`/`take_trace` (called by the node wrapper)
  scope captured LLM/tool calls to one node's `agent_trace`. Matches
  `langchain-core` 1.5.x callback signatures.
- **`app/graph/introspect.py::get_graph_topology(graph)`** — derives
  `{nodes, edges, conditional_edges}` from the live graph via `graph.get_graph()`
  (no hardcoded diagram).
- **`app/graph/workflow.py::stream_triage_graph(raw_input, deps, run_id)`** —
  returns `(generator, bus)`. The generator yields `NodeEvent`s as the graph
  runs (`stream_mode="values"` to capture the cumulative final state without a
  second `invoke`); the bus is threaded through
  `config["configurable"]["event_bus"]`.
- **`app/ui/render_graph.py` / `render_timeline.py` / `render_detail.py` /
  `theme.py`** — self-contained HTML/SVG renderers (no graphviz/agraph/plotly
  dependency) for the three-zone layout. Nodes coloured by status
  (gray/amber/green/red); traversed edges highlighted.
- **`app/ui/streamlit_app.py`** — rewired from `invoke()` to the streaming path.
  Run Triage streams live into a three-zone grid (graph canvas + execution
  timeline | detail panel), then a Final Result + Raw JSON section. Run History
  is stored in `st.session_state["runs"]` (click an entry to re-render a past
  run without re-running the graph). The existing Run Options sidebar
  (Auto-approve, Use LLM-backed agents, LLM provider configured) is unchanged,
  and `use_llm` is now forwarded into `deps` so the investigation orchestrator
  honours the toggle.
- **`app/main.py`** — CLI now consumes `stream_triage_graph`; no leftover
  `invoke()` fallback.