# Integration Decisions

Significant decisions made while integrating the existing agents, graph, mock
data, CLI, and UI into a working end-to-end system. For architecture context
see `README.md` and `incident-triage-HLD.md`.

## Investigation orchestrator architecture

- **The investigation phase is a real LangGraph subgraph owned by the
  orchestrator** (`app/agents/investigation/subgraph.py`): `START` fans out in
  parallel to three sub-agent nodes (`log_analysis`, `kubernetes`, `runbook`),
  which fan in to a `synthesize_outcome` aggregator node. The orchestrator
  (`orchestrator.run_investigation`) is the single owner of the phase — it
  prepares inputs, executes the subgraph, and maps the aggregated result onto
  `InvestigationOutcome`. Subagents therefore run **in parallel** (LangGraph
  fan-out; verified ~3x faster than sequential for slow sub-agents), and the
  sync runbook RAG node is executed in a worker thread so it does not block
  the async branches.
- **Shared state survives the phase**: the aggregator returns structured
  `evidence` / `hypotheses` / `confidence` (plus per-source
  `log_analysis` / `kubernetes_analysis` / `runbook_analysis` /
  `runbook_hypothesis`), which `app/services/investigation_service.py` writes
  into the canonical `IncidentState` — nothing is isolated inside the
  orchestrator. Downstream nodes (`investigation_summary`, `rca_report`,
  verification) consume those state fields; they never re-run the same
  investigation.
- **The orchestrator service is the node's default**: `investigation_node`
  previously fell back to a fake stub when no service was injected; it now
  defaults to the real `investigation_service`, so the orchestrator owns
  investigation on every path (CLI, UI, tests) unless explicitly overridden.
- **Why a subgraph instead of top-level nodes**: the parent triage graph keeps
  a single readable `investigation` node
  (`ingestion → classification → investigation ⇄ verification → summary →
  rca_report → approval → notification`), while the subagent topology,
  parallelism, and aggregation live inside the phase subgraph where they can
  still be executed, tested, and rendered as a first-class LangGraph
  definition (not hand-drawn).
- **Visualization**: `scripts/generate_investigation_png.py` renders
  `docs/investigation_orchestration.png` programmatically from the actual
  subgraph (x-ray view: `investigation_orchestrator` containing its three
  parallel sub-agents and the `synthesize_outcome` aggregator), with plain
  mermaid / graphviz / `.mmd` fallbacks. The orchestrator's never-raise
  degradation contract is preserved: each sub-agent wrapper catches its own
  failures into `info`-severity `Evidence` items.
- **Tests**: `tests/agents/investigation/test_orchestrator.py` covers
  subgraph fan-out structure, subagent invocation, result aggregation,
  shared-state shape, downstream consumption, an end-to-end run through the
  parent graph via the default node path, and sub-agent failure degradation.

## Graph orchestration

- **The graph was already complete** (`app/graph/workflow.py`: ingestion →
  classification → investigation ⇄ verification → summary → rca_report →
  approval → notification, with conditional routing via `app/graph/router.py`).
  No structural graph changes were needed; integration focused on wiring the
  real agent implementations into the `deps` injection points the nodes
  already expose.
- **Investigation node now runs the real sub-agents** via
  `app/agents/investigation/orchestrator.py` +
  `app/services/investigation_service.py` (previously both files were empty
  stubs). The orchestrator coordinates the existing `LogAnalysisAgent`,
  `KubernetesAgent`, and runbook RAG agent; it never raises — a failing
  sub-agent degrades to an `info` Evidence item so one broken dependency
  cannot kill a graph run. See "Investigation orchestrator architecture"
  above for the current subgraph-based design.
- **LLM-optional design**: classification and RCA use LLM-backed agents only
  when explicitly injected (CLI `--use-llm`, UI checkbox gated on API key).
  Investigation/notification services are injected unconditionally because
  they degrade gracefully to deterministic analysis without a key.

## Deterministic investigation semantics

- **Confidence is evidence-driven, not fixed**: the orchestrator computes
  confidence from independent-source convergence (log signals +0.25, degraded
  k8s state +0.2, runbook match +0.15 over a 0.35 base, capped 0.95).
- **A runbook hit alone cannot "resolve" an incident**: with zero
  corroborating telemetry the outcome (and the runbook-derived hypothesis) is
  capped below the 0.5 resolution threshold, so verification correctly routes
  through the reinvestigation loop and ends unresolved. This makes the
  bounded retry loop (`MAX_INVESTIGATION_RETRIES`) actually exercisable.
- **Deterministic k8s analysis only reads the incident's own telemetry**
  (`raw_events`/`raw_alerts`); the mock k8s tool's canned template events would
  otherwise fabricate degradation for incidents that have none.

## Entry points

- **`app/main.py` implemented as a Typer CLI** (was empty). Contract follows
  the pre-existing `tests/test_cli.py`: `app.main:app`, incident JSON path
  argument, `--auto-approve`, exit code 1 with specific stderr messages for
  missing file / invalid JSON / missing `title`/`service`.
- **`app/ui/streamlit_app.py` already invoked `triage_graph` directly** and was
  left structurally untouched; only its `deps` were synced with the CLI
  (investigation + notification services always, LLM services opt-in).
  UI → graph is the only path; no agent is called from the UI.

## Mock data & runbooks

- **`data/incidents/database_timeout.json` title synced** to
  "Database connection pool exhausted on checkout-db" — the CLI contract
  (pre-existing test) asserts the canonical runbook title, and the old title
  broke that.
- **`data/incidents/imagepullbackoff.json` authored** (was an empty `{}`
  placeholder): a real sample whose incident lacks corroborating telemetry, so
  it exercises the unresolved/reinvestigation path end-to-end. All six sample
  incidents now match the `Incident` model schema (`logs`/`events`/`alerts`/
  `metrics`/`metadata` keys consumed by the ingestion node).
- **Runbooks**: no new runbook files were needed — `knowledge_base/runbooks/
  runbook.md` already covers every incident type the samples produce
  (High API Failures, OOMKilled, ImagePullBackOff, HTTP 503, DB Pool
  Exhausted, Third-Party API Timeout, Deployment Regression), and the runbook
  RAG agent retrieves from the ingested FAISS collection.
- **Classification routing hardened**: `THIRD_PARTY`/`DEPLOYMENT` enum values
  (added earlier for the new scenarios) were missing from the classification
  node's `_TYPE_KEYWORDS`/`_TEAMS_BY_TYPE` — an LLM classification returning
  them would have raised `KeyError`. Both now route (THIRD_PARTY →
  BACKEND/NETWORK, DEPLOYMENT → SRE/BACKEND).

## Infrastructure fixes

- **Embeddings are offline-first** (`app/knowledge/embeddings.py`): the
  sentence-transformers model is loaded with `local_files_only=True` (with a
  network fallback only if the cache is cold). Previously every runbook
  retrieval attempted a Hugging Face round-trip and failed in
  restricted-network environments.

## Investigation subagent execution fix (2026-08-26)

### Root cause

Investigation subagents were not executing. The investigation phase graph
(`app/agents/investigation/subgraph.py`) used `builder.add_node(name, fn)`
where `builder` was a raw `StateGraph` instance from `create_graph()`. This
called `StateGraph.add_node()` directly, bypassing the wrapper in
`app/graph.builder.add_node()` that adds `[NODE][ENTRY]` / `[NODE][EXIT]`
logging. Additionally, the builder wrapper was a **sync function** wrapping
**async node functions** — it returned unawaited coroutines, breaking
LangGraph's async dispatch. In deterministic mode (no LLM), the orchestrator's
`_log_evidence` and `_kubernetes_evidence` used inline keyword fallbacks
instead of delegating to the agents, so `LogAnalysisAgent` and
`KubernetesAgent` never actually executed.

### Fixes applied

1. **`app/graph/builder.py`**: Rewrote `_wrap_node_with_logging` to preserve
   async-ness. Async node functions get an `async def` wrapper; sync nodes get
   a `def` wrapper. Uses `[NODE][ENTRY]` / `[NODE][EXIT]` format via shared
   `app/logging_utils.py`.

2. **`app/agents/investigation/subgraph.py`**: Changed to import `add_node`
   and `add_edge` from `app.graph.builder` and call them as free functions
   (`add_node(builder, name, fn)`) instead of as instance methods
   (`builder.add_node(name, fn)`). This ensures the logging wrapper is applied.

3. **`app/agents/investigation/log_analysis/agent.py`** and
   **`app/agents/investigation/kubernetes/agent.py`**: Added
   `analyze_logs_with_fallback()` / `analyze_kubernetes_with_fallback()` that
   **always execute** the agent (LLM when available, deterministic keyword
   fallback internally). Added `[SUBAGENT][ENTRY]` / `[SUBAGENT][OUTPUT]` /
   `[SUBAGENT][EXIT]` lifecycle logging.

4. **`app/agents/investigation/orchestrator.py`**: Updated `_log_evidence` and
   `_kubernetes_evidence` to always delegate to the new `*_with_fallback`
   functions instead of using inline keyword fallbacks. Added `[AGENT]`
   lifecycle logging to `run_investigation`.

5. **`app/logging_utils.py`**: New shared module providing consistent
   `[NODE]` / `[AGENT]` / `[SUBAGENT]` lifecycle logging with ENTRY / OUTPUT /
   EXIT / ERROR tags. Used by all agents, subagents, and the builder wrapper.

### Validation

- All 101 tests pass.
- CLI trace shows the full lifecycle:
  `[NODE][ENTRY] investigation` → `[AGENT][ENTRY] InvestigationService` →
  `[AGENT][ENTRY] InvestigationOrchestrator` → `[SUBAGENT][ENTRY] LogAnalysisAgent`
  → `[SUBAGENT][EXIT] LogAnalysisAgent` → `[SUBAGENT][ENTRY] KubernetesAnalysisAgent`
  → `[SUBAGENT][EXIT] KubernetesAnalysisAgent` → `[SUBAGENT][ENTRY] RunbookAgent`
  → `[SUBAGENT][EXIT] RunbookAgent` → `[AGENT][EXIT] InvestigationOrchestrator`
  → `[AGENT][EXIT] InvestigationService` → `[NODE][EXIT] investigation`
- All three subagents execute in both LLM-backed and deterministic modes.

## Testing & validation

- `tests/graph/test_workflow.py` (15 tests): compilation + node/edge presence,
  resolved end-to-end flow over all rich mock samples, per-source state
  propagation (`log_analysis`/`runbook_analysis`/`kubernetes_analysis`),
  conditional-routing unit tests, the unresolved retry loop, final report
  renderability, and injected agent-failure handling.
- All tests run on deterministic fallbacks — no network or API key required.
- Graph visualization: `scripts/generate_graph_png.py` renders
  `docs/triage_graph.png` via langgraph's Mermaid renderer (graphviz PNG and
  raw `.mmd` fallbacks included for environments without network).
