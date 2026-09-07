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

---

# Phase 1 Audit — Evidence-Grounded Investigation Pipeline (source of truth for later phases)

Audit performed per `master_accuracy_mockdata_instructions.md` Phase 1. This
section is the ground truth for Phases 2–10. All paths are relative to the
repo root `ai-incident-triage/`.

## 1. Where each pipeline output is currently produced

| Output | Produced by | Notes |
|---|---|---|
| incident input/normalization (ingestion) | `app/graph/nodes/ingestion.py` → `_default_ignest` (empty `app/services/ingestion_service.py`, so the node fallback is what runs) | Builds the domain `Incident` from `raw_input`; writes `incident`, `incident_id`, `normalized_input` (= `incident.model_dump()`), `investigation_status=NEW`. |
| evidence collection (logs, k8s, other diagnostics) | Investigation Orchestrator `app/agents/investigation/orchestrator.py` → subgraph `app/agents/investigation/subgraph.py` (3 parallel sub-agents fan-out → `synthesize_outcome`) | Three evidence items always created: `ev-log-1`, `ev-k8s-1`, `ev-rb-1`. Written to state via `app/services/investigation_service.py` (`evidence`, `hypotheses`, plus per-source `log_analysis`/`kubernetes_analysis`/`runbook_analysis`). |
| log-analysis sub-agent | `app/agents/investigation/log_analysis/agent.py` (`LogAnalysisAgent`) | RAG retrieval over `logs` FAISS collection (from `model-data`), LLM-backed with deterministic keyword fallback `_deterministic_analysis`. `LOG_COLLECTION="logs"`. |
| Kubernetes diagnostics sub-agent | `app/agents/investigation/kubernetes/agent.py` (`KubernetesAgent`) | RAG retrieval over `k8s` collection (`K8S_COLLECTION="k8s"`); cross-incident service filtering via `_services_relate`; `degraded = bool(hypotheses)`. |
| runbook retrieval/matching | `app/agents/investigation/runbook/agent.py` + `resolver.py` | **Two mechanisms, see §2 below.** |
| hypothesis generation | `_synthesize_outcome` in `orchestrator.py` | `hyp-1` primary + optional runbook hypothesis; label LIKELY (≥0.7) / POSSIBLE; confidence heuristic (§6 below). |
| RCA synthesis | `app/graph/nodes/rca_report.py` → `_default_rca_report`, or real `app/services/rca_report_service.py` (LLM-backed `app/agents/rca_report/agent.py`) | Picks top hypothesis by confidence as `RootCauseAnalysis.primary_cause`; builds `expected_outcome` dict. |
| report generation | `app/services/rca_report_service.py` `render_markdown_report` (+ `build_incident_report`) | Deterministic — assembles/render only; never calls an LLM itself. |
| notification generation | `app/agents/notification/agent.py` (LLM draft `/template fallback `_draft_email_template`) → Resend (`app/tools/adapters/resend_email.py`), simulated when no `RESEND_API_KEY` | Prompt template `app/prompts/templates/notification.txt`. |
| verification / resolution-state | `app/graph/nodes/verification.py` → `_default_verify` (empty `app/services/verification_service.py`) | **BUG (Phase 4 target): marks `RESOLVED` if `confidence_score ≥ 0.5` AND `expected_outcome.action` exists — conflates RCA confidence with resolution; no fix-applied / recovery evidence required.** Also `_default_notify` sets `RESOLVED`/`UNRESOLVED` from verification. |

## 2. Runbook storage + matching keys (critical for Phase 7)

- **Existing runbook files live in TWO places:**
  1. Top-level `runbooks/*.md` — 4 files (`database-connection-failure.md`, `high-api-latency.md`, `high-cpu-saturation.md`, `pod-crash-loop.md`). Each follows `# <Incident Display Name>` → `## Overview` → `## Solution` → `## Troubleshooting`. **The name-based resolver and the tests key on these.**
  2. `knowledge_base/runbooks/runbook.md` — one curated multi-incident index (7 `##` sections: High API Failures, Pod CrashLoopBackOff (OOMKilled), ImagePullBackOff, HTTP 503, Database Connection Pool Exhausted, Third-Party API Timeout, Deployment Regression). Loaded by `app.knowledge.model_data.runbook_md()`.
- **Matching logic keys on:**
  1. `resolver.resolve_by_name` (`app/agents/investigation/runbook/resolver.py`): token-overlap between the incident display name (`# ` heading in each `runbooks/*.md`) and incident title/description; returns only docs with a real `## Solution`; path = `Path(__file__).resolve().parents[4] / "runbooks"` (repo root).
  2. Semantic FAISS `runbooks` collection: `retrieve(collection="runbooks", query_text, k=3)`, `MIN_RELEVANCE_SCORE = 0.45` (cosine). Collection is populated by `scripts/ingest_model_data.py` `_ingest_runbooks()` from BOTH `knowledge_base/runbooks/runbook.md` AND `runbooks/*.md`.
  - **Consequence:** a named runbook only reaches the final result via `resolver.resolve_by_name` (top-level `runbooks/`). A runbook that lives ONLY in `knowledge_base/` is retrievable by FAISS (relevance evidence) but never name-matched, so `runbook_name`/`runbook_solution` stay `None`. **Phase 7 must therefore place each new standalone runbook file in top-level `runbooks/*.md` AND re-run `python scripts/ingest_model_data.py` for the FAISS collection.**
- **Phase 6.2 runbook-name note:** the `metadata.runbook` field (e.g. INC-006 → `"Database Connection Failure"`) currently exists in only some incident JSONs and is not read by the resolver.

## 3. Exact field names confirmed

- State schema: `app/graph/state.py` (`IncidentState`, `total=False`). Key fields:
  - `incident_id`, `incident: Incident`, `raw_input`, `normalized_input`
  - `classification: ClassificationResult`, `incident_type`, `severity`, `classification_confidence`
  - `investigation_status: IncidentStatus`, `evidence: list[Evidence]`, `hypotheses: list[Hypothesis]`
  - `log_analysis` / `runbook_analysis` / `kubernetes_analysis: Evidence`
  - `runbook_name: str|None`, `runbook_solution: str|None`
  - `investigation_summary: dict` (keys: `summary`, `evidence_count`, `hypothesis_count`, `top_hypothesis_id`, `sources`)
  - `root_cause: RootCauseAnalysis`, `rca_confidence: float`, `incident_report: IncidentReport`
  - `expected_outcome: dict`, `verification_result: VerificationResult`, `is_resolved: bool`
  - `retry_count`, `current_step`, `errors`, `approval`, `approval_status`, `notification_status`, runbook-learning fields, `guardrail_findings`
- **`evidence`** = `list[Evidence]`: `evidence_id`, `source` (`"log_analysis"|"runbook"|"kubernetes"`), `finding`, `severity` (`"high"|"medium"|"info"`), `raw_data` (dict), `timestamp`.
- **`hypotheses`** = `list[Hypothesis]`: `hypothesis_id`, `description`, `confidence`, `supporting_evidence` (evidence IDs), `contradicting_evidence`, `label` (`HypothesisLabel`: LIKELY/POSSIBLE/UNLIKELY).
- **`root_cause`** = `RootCauseAnalysis`: `primary_cause: Hypothesis`, `contributing_factors: list[Hypothesis]`, `confidence_score: float`, `timeline: list[TimelineEvent]`, `affected_components: list[str]`.
- **`confidence`** — three separate values, don't conflate: `classification.confidence`, `hypothesis.confidence`, `root_cause.confidence_score` (= top hypothesis confidence) + state scalar `rca_confidence`.
- **`investigation_status`** — `IncidentStatus` enum: `NEW, TRIAGING, INVESTIGATING, RESOLVED, UNRESOLVED, ESCALATED, CLOSED`.
- **`is_resolved`** — plain `bool`, set by verification node, mirrored in `VerificationResult.is_resolved`.
- **`recommended_actions`** — `list[str]` on `IncidentReport`; derived that may include runbook text.
- **`expected_outcome`** — dict with exactly two keys: `expectation` (str) and `action` (str). **Verification's `resolved` check keys on `expected_outcome.action` being truthy.**
- **notification/email text** — `NotificationEmail` dataclass `{subject, body}` (HTML body). Prompt template says "resolved incident's RCA report" and asks for "the resolution steps taken" — **Phase 5 target** (the `[Resolved]`/`Resolution steps taken` wording problem).

## 4. Mock-data schema + log format (must match for Phase 6)

- **Incident JSONs (`data/incidents/*.json`) use TWO INCONSISTENT key conventions:**
  - Non-`raw_` keys: `logs`/`events`/`alerts`/`metrics` (crashloopbackoff, database_timeout, http503, imagepullbackoff, unmatched-no-telemetry).
  - `raw_` keys: `raw_logs`/`raw_events`/`raw_alerts`/`raw_metrics` (INC-006 database-connection-failure, auth-config-mismatch, memory-oom, pod-crash-loop, high-api-latency, high-cpu-saturation, application-error-spike, dependency-cache-down, network-connectivity, deployment_regression, third_party_timeout).
  - **`_default_ignest` reads ONLY the non-`raw_` keys** (`raw.get("logs")`, `raw.get("events")`, `raw.get("alerts")`, `raw.get("metrics")`). So the 11 `raw_*` incidents currently ingest with EMPTY telemetry (`raw_logs=[]`, `raw_metrics={}`). **Phase 6 must standardise on ONE schema and Phase 1/2 must decide which.** (The model fields are `raw_logs`/`raw_events`/`raw_alerts`/`raw_metrics`.)
  - Common fields: `incident_id`, `title`, `description`, `source`, `service`, `environment` (uppercase enum string), `priority_hint` (P1–P4), `tags`, `timestamp` (ISO-8601), `metadata` (free dict; some carry `scenario_id`, `namespace`, `runbook`).
- **Log formats in `model-data/` (RAG source for `logs` collection) do NOT use the `sequence`/`loggerClassName`/`IMAGE_TAG` schema shown in the Phase 6 work example.** Actual formats:
  - `db_logs.txt`: plain text lines `2026-08-06T10:33:05.000Z LOG [analytics-replica] ...` (service from `[bracket]`).
  - `external_api_logs.txt`: plain lines `... OUTBOUND payment-service -> https://... result=TIMEOUT http_status=- elapsed_ms=8000`.
  - `logs_traces.txt`: one JSON object per line `{"timestamp","level","service","trace_id","span_id","http":{"method","url","status","latency_ms"},"message"}` (+ nginx + class-logger lines).
  - `incident_telemetry_logs.txt`: header states keyed `[service]`, INC-006..INC-014.
  - Service extraction (`app/knowledge/model_data.py::_service_from_txt`): `[bracket]` → `"service":` JSON → nginx `"GET "` → web-gateway → `(ERROR|WARN|INFO|DEBUG) com.x.y.` class regex → else `unknown`. **Phase 6 JSON logs with `loggerName:"com.mockcorp..."` and `level` will NOT yield a service token with this logic → will bucket as `unknown` and be non-retrievable per-service.** Verify against Phase 6 worked example (`sequence`/`loggerName`/`IMAGE_TAG`...).
  - Chunking: `_chunk_by_service` groups by service, bucket_size 40.
- **`model-data` → FAISS mapping** (`scripts/ingest_model_data.py` + `app/knowledge/model_data.py`):
  - `db_logs.txt`, `external_api_logs.txt`, `logs_traces.txt`, `incident_telemetry_logs.txt` → `logs`
  - `metrics.json`, `incident_metrics.json` → `metrics` (schema `{timestamp, service, pod_name, metric_name, value}`)
  - `k8s_logs.json`, `incident_k8s.json` → `k8s` (schema `{timestamp, pod_name, namespace, log_level, message}`)
  - `deployment_events.json` → `events` (schema `{timestamp, service, deploy_version, event_type, initiated_by}`)
  - `knowledge_base/runbooks/runbook.md` + `runbooks/*.md` → `runbooks`
  - Vector store: local FAISS under `vectorstore/` (`settings.vector_store_path`), embeddings `sentence-transformers/all-MiniLM-L6-v2`, collections `logs`,`k8s`,`metrics`,`events`,`runbooks`. Rebuilt via `python scripts/ingest_model_data.py` (idempotent).
- **Incident JSON raw_logs** (plain strings) are ALSO passed to the log agent; but since the log agent prefers the RAG `logs` collection, raw_logs only matter when RAG is missing (`No log evidence available`).

## 5. Where LLM-generated statements can masquerade as evidence

- The orchestrator's `Evidence` items are built from each sub-agent's result object, but the `finding` strings originate from:
  - log agent: LLM-generated `LogAnalysisResult.summary`/evidence, or deterministic fallback.
  - k8s agent: LLM `KubernetesAnalysisResult` summary / evidence, or deterministic fallback.
  - runbook agent: pure RAG (no chat LLM).
- So an `Evidence`-shaped object is **not proof of observation** until its origin is traced to telemetry. Phase 2 must add an explicit provenance category (`OBSERVED/REPORTED/CONTEXT/INFERRED`) to `Evidence`/claims and ensure empty `raw_logs`/`raw_metrics`/events can never produce "confirmed" findings.
- Race condition/order caveat: `_log_evidence` and `_kubernetes_evidence` read from the shared `logs`/`k8s` RAG collections which are per-service chunked — cross-incident contamination is possible when two incidents share a service; Phase 8 addresses this (incident-scoped retrieval).

## 6. Confidence heuristics in the orchestrator (Phase 3/4 target)

- Base `0.35`; +0.25 if log severity `high`; +0.2 if k8s severity != `info`; +0.15 if runbook hypothesis exists; capped `0.95`; floor `0.45` when both log & k8s are `info`. `DEFAULT_CONFIDENCE_SCORE = 0.5` gates resolution. Runbook-only matches are clamped ≤0.45 (never resolve alone) — already partially aligned with Phase 4, but resolution is STILL gated only on confidence + boolean action, not real recovery evidence.

## 7. Tests/conventions (Phase 9 target)

- `tests/conftest.py` stubs `app.agents.notification.agent.send_email`.
- Tests load incidents from `INCIDENTS = Path(__file__).resolve().parents[2] / "data" / "incidents"` and run `triage_graph.invoke({"raw_input": raw}, deps={auto_approve, investigation_service, notification_service})`.
- Current assertions that Phase 2–5 must break/adjust: several incidents (database_timeout, http503, crashloopbackoff, third_party_timeout, deployment_regression) assert `is_resolved is True`; `test_runbook_backed_incident_cites_runbook_in_final_result` asserts runbook solution in `expected_outcome.action`; `test_unresolved_incident_loops_then_terminates_unresolved` asserts `INC-SIM-3001` unresolved.
- Test commands: `pytest` (Uses normal pytest discovery). Agent/UI conventions documented in NOTES.md above.

## 8. Other observations for later phases

- `app/services/ingestion_service.py`, `verification_service.py`, `evidence_service.py`, `hypothesis_service.py` are **empty** — the node fallbacks are the real logic. Phase 2/3 will likely implement the real services here.
- `scripts/seed_mock_data.py` is empty. `data/incidents/README.md` is stale (says 4 placeholder files; directory now has 16 real JSON + README).
- `data/outcomes/{resolved,unresolved}` and `data/reports/` exist (outcomes contain files; reports contains only `.gitkeep`).
- Runbook Learning loop (`app/services/runbook_learning_service.py`) appends `## Observed Incident` sections only when `verification.is_resolved`; it also writes to `Path("knowledge_base/runbooks")` (relative CWD) — Phase 4 changes (never resolving without external evidence) will make this loop skip for B–L/INC-006. Note it also ingests `runbook_learning_file_touched` into the FAISS `runbooks` collection.
- Priority enum: P1–P4 (see `app/domain/enums/priority.py`); `ClassificationResult` has `incident_type, priority, confidence, reasoning, affected_services, suggested_teams, rule_based_priority, agrees_with_rule`.
- IncidentType keywords / team mapping live in `app/graph/nodes/classification.py`.
- No checkpointing; each run is ephemeral; recursion limit 50.

## 9. DATA-LOCATION DISCREPANCIES vs. the user's stated phase mapping

User mapping (from the phase gating instruction): logs → `model-data`; runbooks → `knowledge_base`; incidents → `incidents` folder.

| Data | User mapping | Actual location (Phase 1) | Status |
|---|---|---|---|
| Log data (+ Phase 6 logs) | `model-data` | `model-data/` (9 files) | ✅ matches |
| Runbook files (existing + 11 Phase 7) | `knowledge_base` | Top-level `runbooks/*.md` (4 files, name-matched + tested) AND `knowledge_base/runbooks/runbook.md` (FAISS index) | ⚠️ BOTH — resolver & tests key on top-level `runbooks/` |
| Incident records (existing + Phase 6) | `incidents` folder | `data/incidents/` (16 JSON + README); `knowledge_base/incidents/` exists but is empty (`.gitkeep` only) | ⚠️ no `incidents/` folder exists |

**This must be confirmed with the user before Phase 2 per the phase-gating instruction** (do not create new files until resolved). Recommended resolution given the code: keep incidents in `data/incidents/` and place Phase 7 runbook files in top-level `runbooks/` (to satisfy the resolver + tests), while still mirroring into `knowledge_base/` if the user insists the canonical home is `knowledge_base`.
## 10. Phase 2 — Evidence Provenance & Grounding Model (COMPLETE)

Decision on §9 (user-confirmed): keep incidents in `data/incidents/`; Phase 7 runbooks go to top-level `runbooks/*.md` and get re-ingested; `knowledge_base/incidents/` stays unused. Phase 2 implemented.

### Provenance enum
- New `app/domain/enums/provenance.py`: `EvidenceProvenance` (str Enum) = `OBSERVED | REPORTED | CONTEXT | INFERRED`. Exported from `app/domain/enums/__init__.py`.
- `Evidence` gains `provenance: EvidenceProvenance = REPORTED` (conservative default).
- `Hypothesis` gains `provenance: EvidenceProvenance = INFERRED` (a hypothesis is a derived conclusion).
- Additive: all existing constructors/tests continue to work with the defaults.

### Grounding rules implemented
- Log agent (`app/agents/investigation/log_analysis/agent.py`): deterministic + LLM paths now expose `telemetry_signals`, `telemetry_available`, `unavailable_reason` in `raw_data`. New `_services_relate` guard (mirrors k8s): retrieved model-data documents count as this incident's telemetry ONLY when they belong to the incident's service. No telemetry → finding states "no grounded log evidence" (info/REPORTED), never "confirmed".
- K8s agent (`.../kubernetes/agent.py`): same gating (`service_relevant` → `telemetry_signals`, `telemetry_available`); degradation (`severity=medium`) requires signals in OWN cluster events or service-matching retrieved docs. Alert names/descriptions alone never mark a workload degraded.
- Runbook agent + orchestrator `_runbook_evidence`: runbook evidence AND hypotheses always `provenance=CONTEXT` (guidance, never proof).
- Orchestrator: `_log_evidence` no longer recomputes severity from description/alert keywords; severity = `telemetry_available` AND agent `telemetry_signals`. When no telemetry, overconfident LLM summaries are replaced with an explicit "cannot confirm" statement (via `_looks_like_confirmation`). `_synthesize_outcome` primary hypothesis = INFERRED; k8s evidence keeps agent-set provenance; both agents now set `telemetry_available` in `raw_data`.
- RCA agent `_reconcile_with_ceiling` forces primary_cause + contributing_factors to INFERRED (deterministic boundary).
- Prompts updated: `log_analysis.txt`, `kubernetes.txt` (add provenance to JSON schema + no-confirmation-without-logs rule), `rca_report/prompt.py` (provenance surfaced in evidence lines + CONTEXT-never-proof instruction).
- Markdown report (`rca_report_service.py`) now renders provenance per evidence + hypothesis.

### Evidence-availability guards (the known bug)
- `raw_logs=[]` + description/alerts containing signal keywords → severity stays `info`, provenance `REPORTED`, finding explicitly says no log telemetry. (Encoded in `test_log_with_zero_telemetry_is_reported_and_never_high`.)
- Empty k8s events + unrelated retrieval → `info`, `REPORTED`, "none belong to service ... unknown" (no cross-incident contamination).
- Metrics: no code path generates metric-confirmed findings (none existed); empty `raw_metrics` never asserted as evidence.

### Bug found & fixed during verification
Cross-incident contamination: initial implementation counted ANY retrieved model-data doc as the incident's telemetry. For the unsynchronized service `graviton-scheduler` (INC-SIM-3001 / unmatched-no-telemetry), retrieval surfaced unrelated services' docs (`checkout`, `payments`) containing "error/fail" → log/k8s severity became high/medium → confidence 0.95 → incident RESOLVED, breaking `test_unresolved_incident_loops_then_terminates_unresolved`. Fixed by gating retrieved telemetry on `_services_relate` (both agents) and by orchestrator honoring `telemetry_available`. Verified: unmatched-no-telemetry stays unresolved (confidence 0.45) even under a polluted runbook index.

### Test-isolation discovery (pre-existing, NOT Phase 2)
Running the workflow suite mutates fixtures: resolving incidents triggers `runbook_learning_service` which appends `## Observed Incident` to top-level `runbooks/*.md` AND `knowledge_base/runbooks/*.md` and re-ingests into the FAISS `runbooks` collection (modifying `vectorstore/runbooks/index.faiss` + `metadata.json`), and creates untracked `knowledge_base/runbooks/<name>--<service>--<env>.md` files. Consequence: a second full-suite run can fail `tests/knowledge/test_model_data_retrieval.py::test_runbook_collection_contains_named_runbooks` (Solution heading not found in a chunk) due to the shifted index. Mitigation used during Phase 2 testing: run `tests/knowledge` on a clean index first, then restore `runbooks/`, `vectorstore/` and `git clean -fd knowledge_base/runbooks/`. Consider fixing the learner's test hygiene in a later phase (e.g. only write when OUT dir configured, or fixture-stub).

### Phase 2 verification
- New `tests/agents/investigation/test_provenance.py` (9 tests, deterministic, no LLM) locks defaults, log/k8s gating, runbook=CONTEXT, synthesis=INFERRED, and the no-telemetry guard.
- Full run on clean fixtures: `tests/knowledge` (10) + `tests/services/test_rca_report_service.py` (12) + `tests/agents`, `tests/graph`, `test_runbook_learning.py` (52) all green. Only pre-existing/unrelated failure: `tests/telemetry/test_tracing.py::test_returns_handler_when_configured` (ModuleNotFoundError: langfuse; fails on pristine too).
- Ruff: no new error classes beyond the file baseline (UP modernization style + pre-existing F821 `RunbookDoc`); new test file is ruff-clean.

## 11. Phase 3 — Deterministic Claim Validation & Confidence Calibration (COMPLETE)

### Scope (from master Phase 3)
Validate RCA claims deterministically (code, NOT a second LLM) BEFORE the RCA is finalized, and calibrate the confidence score. Reject/downgrade claims that telemetry cannot support:

- OOMKilled without an OOMKilled / exit-code-137 / out-of-memory / restart signal
- CrashLoopBackOff without matching Kubernetes state/events attached to the incident
- CPU saturation without CPU metric keys in `raw_metrics` (heap usage must NOT satisfy this)
- "database down / unreachable" when the evidence only shows connection-pool exhaustion
- recovery ("service recovered/stabilized") without post-remediation recovery evidence (never verified)
- runbook-symptom-only claims (flagged, but not penalized — runbook similarity is purely a relevance signal)
- claims whose cited-cited "evidence" came from an empty source (report-declared severity info, `telemetry_available=False`)

Confidence rules honored: observed telemetry outweighs description text; multiple independent sources increase confidence; runbook similarity drives runbook relevance, never RCA certainty directly; missing telemetry lowers confidence; contradictions reduce confidence; inference cannot exceed supporting evidence (weighted ceiling).

### Where it plugs in
- `app/domain/models/claim_validation.py` (new): `ClaimCategory` (OOMKILLED, CRASHLOOPBACKOFF, CPU_SATURATION, DB_OUTAGE, RECOVERY, RUNBOOK_ONLY, EMPTY_SOURCE) and `ClaimValidationFinding` (hypothesis_id, category, claim, supported, penalty, qualifier, detail).
- `app/domain/models/root_cause.py`: `RootCauseAnalysis.claim_validation: List[ClaimValidationFinding]` (default empty → LLM-parser / existing callers unaffected).
- `app/services/evidence_service.py` (was empty): `validate_hypotheses(incident, evidence, hypotheses)`. Corpus = cited observed evidence findings + incident raw logs/alerts/events/metrics (optionally named). Detectors as above.
- `app/services/hypothesis_service.py` (was empty): `calibrate_hypotheses` (apply penalties, re-label LIKELY ≥0.7 / POSSIBLE ≥0.4 / UNLIKELY) and `finalize_root_cause` (penalize the primary, cap with `compute_confidence_ceiling`, append `description` qualifiers, attach findings to `RootCauseAnalysis.claim_validation`).
- Wired into both RCA paths: `app/graph/nodes/rca_report.py::_default_rca_report` and `app/services/rca_report_service.py` (after `generate_root_cause_analysis`).

### Penalty & qualifier table
| Category | Penalty | Qualifier example |
|---|---|---|
| OOMKilled, unsupported | 0.15 | "reported OOMKilled; no OOMKilled / exit-code-137 / restart signal in observed telemetry" |
| CrashLoopBackOff, unsupported | 0.15 | "no matching Kubernetes state/events in observed telemetry" |
| CPU saturation, no CPU metric | 0.15 | "no CPU metrics present" |
| DB outage, reword to pool exhaustion | 0.0 | "the pool was exhausted, not a DB outage" |
| DB outage, no DB telemetry | 0.15 | "no database outage telemetry present" |
| Recovery, INFERRED | 0.10 | "no post-remediation recovery evidence; recovery claimed but not verified" |
| Recovery, CONTEXT (runbook) | 0.0 | — (no penalization) |
| Runbook-only symptom | 0.0 | "symptom not independently verified" |
| Empty source evidence | 0.15 | "telemetry unavailable; evidence is a report, not observed data" |

Per-hypothesis total penalty capped at 0.25; penalties apply ONLY downward (never raise confidence).

### Ceiling design (verified against the 6-incident resolution locks)
`finalize_root_cause` re-applies `compute_confidence_ceiling([primary, *contributing])` with LIKELY=1.0 / POSSIBLE=0.6 / UNLIKELY=0.25 label weights:
- All 5 resolving incidents (database_timeout, crashloopbackoff, http503, third_party_timeout, deployment_regression) have LIKELY primaries → weight 1.0 → confidence UNCHANGED.
- unmatched-no-telemetry (graviton-scheduler, POSSIBLE 0.35) → ceiling 0.35×0.6 = 0.21. Was unresolved before, stays unresolved (Phase 4 will harden this further).

### Bug found & fixed during verification
1. k8s finding quoting cross-service signals: for `database_timeout` the k8s finding quoted "CrashLoopBackOff, OOMKilled, restart" signals from OTHER services' retrieved docs (orders-worker/payments) while checkout's own degradation was only timeouts. Reordered `_deterministic_analysis` branches in `app/agents/investigation/kubernetes/agent.py` so `retrieved and not service_relevant` + degraded uses the incident's OWN attached-event signals. All six incidents verified to keep severity/provenance/confidence after the fix.
2. Fallback-path regression: applying the ceiling to the no-hypotheses fallback (0.5 POSSIBLE → 0.3) broke `test_agent_failure_is_caught_and_recorded_not_raised` (the failing-investigation stub never increments retry_count, so the unresolved loop spun to the 50-step recursion limit). Fix: `_default_rca_report` only runs `finalize_root_cause` when the investigation produced hypotheses; with none there are no claims to validate and the pre-Phase-3 fallback resolution semantics are preserved (Phase 4 is where resolution gating belongs).

### Verification
- New `tests/services/test_claim_validation.py` (19 deterministic tests): detector unit tests, calibration re-label + downgrade, finalize qualifier + label-weighted ceiling, supported-RCA untouched, multi-category penalty cap, and graph-node / service wiring (claim_validation present in update + attached to typed RCA).
- Full run: `tests/knowledge` (10) + `tests/services` (18) + `tests/agents`+`tests/graph`+`test_runbook_learning.py` (61) — all green (workflow 15/15, including the resolution-locking tests). Same pre-existing `langfuse` telemetry failure only.
- Ruff: 4 new files (claim_validation model, evidence_service, hypothesis_service, test) fully clean; touched files add no NEW error classes vs pristine baseline (UP006/045/037/035 + C408/UP017/BLE001/I001 remain repo-wide modernization debt; fixed ISC004/SIM103 + import ordering introduced in this phase).
- Fixtures restored after the polluting graph run (`git checkout -- runbooks/ vectorstore/` + `git clean -fd knowledge_base/runbooks/`).

### Carry-over to Phase 4
`_default_verify` currently resolves when `confidence_score >= 0.5` AND `expected_outcome.action` truthy. Phase 4 must require actual external evidence (e.g., observed recovery) before resolution, per master. The fallback-hypothesis path (0.5 → resolves) becomes a Phase 4 concern; Phase 3 intentionally preserved it.

## 12. Phase 4 — Decouple confidence from resolution; gate resolution on real evidence (COMPLETE)

### Scope (from master Phase 4)
RCA confidence and resolution status are separate concepts. The pipeline is investigate-only (no remediation executor), so RESOLVED must never be inferred from diagnosis alone -- no high confidence, runbook match, or expected action resolves on its own. `RESOLVED` requires explicit, externally-supplied evidence of recovery; without it the state stays non-resolved (investigated / remediation pending).

### Implementation
- `app/services/verification_service.py` (was empty): the full gate.
  - `rca_basis_met` = RCA exists AND `confidence_score >= DEFAULT_CONFIDENCE_SCORE` (0.5) AND an expected action is present (inherited requirement).
  - `recovery_signals = _detect_recovery_signals(incident)`: positive-restoration-language patterns scanned over the incident's RAW TELEMETRY ONLY (`raw_logs`, `raw_events`, `raw_alerts`, `raw_metrics`). Never the incident description, runbook text, or diagnosis output.
  - `resolved = rca_basis_met AND recovery_signals is not None`.
  - `resolution_evidence` states exactly which signals matched plus that the fix was never applied by this system.
- Recovery patterns cover the checklist: error-rate / 429-5xx returning to baseline, queue/waiting/pool normalized or cleared, latency normalized, pod/crash state cleared or restart-success, readiness healthy, cpu/memory/disk back to safe range, explicit "recovered", services/operations/connectivity "restored". Every pattern requires POSITIVE language so degradation markers can never fire: "readiness probe failed, pod not ready", `AuthServiceZeroHealthyEndpoints`, `readiness_failures: 4`, "recovering connection" all verified non-matching.
- Retry accounting now OWNS in the verification service (`retry_count` incremented exactly once per reinvestigation request) instead of `investigation_service`. Previously the counter only grew on *successful* investigations, so a repeatedly-failing investigation could spin to the graph recursion limit; now the bounded loop always terminates (also makes the loop exactly 3 runs vs the old 4-run off-by-one).
- `app/graph/nodes/verification.py`: removed the inline confidence-only `_default_verify`; node defaults to `verification_service` (same `deps["verification_service"]` override surface).

### Behavior change (intentional, per master checklist lines 464/476/510)
- NO mocked incident resolves anymore: all 12 are investigation/recommendation scenarios by design and none carries external recovery telemetry. High-confidence incidents (database_timeout 0.95, crashloopbackoff 0.95, http503/third_party/deployment 0.75) now terminate at notification as UNRESOLVED after the bounded reinvestigation loop.
- API/CLI behavior: `is_resolved` always False for these incidents; `investigation_status` UNRESOLVED; `notification_status` NOTIFIED (remediation-pending notification).
- Side benefit: runbook-learning (gated on `verification.is_resolved`) never fires in the graph flow, so the workflow suite no longer pollutes `runbooks/` / `vectorstore/` / `knowledge_base/runbooks/` fixtures.

### Tests updated (required by the redefined semantics)
- `tests/graph/test_workflow.py`: `test_end_to_end_database_timeout_resolves` → `test_end_to_end_database_timeout_identifies_rca_without_resolving` (asserts unresolved + loop ran + notified); `test_all_rich_mock_incidents_flow_end_to_end` now asserts `is_resolved is False`; `test_unresolved_incident_loops_then_terminates_unresolved` unchanged (all incidents now follow that path).
- `tests/agents/investigation/test_orchestrator.py::test_end_to_end_via_default_orchestrator_node`: `is_resolved` assertion flipped to False.
- New `tests/services/test_verification_service.py` (16 deterministic tests): the core "high confidence + action + NO recovery stays unresolved" decoupling; recovery-signal resolving; below-threshold / no-action / no-RCA never resolve even with signals; description-word recovery does NOT count; degradation markers are not recovery; runbook match alone never resolves; retry accounting (increments on unresolved only, once per attempt); incident-report sync.

### Verification
- `tests/knowledge` + `tests/services`: 56 passed. `tests/agents` + `tests/graph` + `test_runbook_learning.py`: 61 passed. Fixtures clean before AND after (no runbook/vectorstore mutation).
- Ruff: new `verification_service.py` and `test_verification_service.py` clean; node/business edits introduce no new error classes (UP045 `Optional[RunnableConfig]` + BLE001 match the existing 7-node convention).

### Carry-over to Phase 5
Phase 5 is the canonical report/notification template. The rendering currently still says "✅ Resolved"/"❌ Not resolved" (`app/services/rca_report_service.py:214`) and the master wants the exact Phase 5 structure with `Remediation: Not Applied`, "Investigation: Completed" != resolved, etc. Phase 5 also inherits Phase 4's guarantee that the template is fed only the validated RCA (report generator must not re-interpret).

---

## Phase 5 (section 13): Canonical report & notification template

### Scope (from master Phase 5)
Every generated report and notification must follow an exact structure and population rules; the text must never over-claim. "Investigation: Completed" is not "resolved". Root cause is reported in one of three allowed states. Remediation is `Not Applied` / `Applied` / `Pending On-Call Action`. No report/notification ever claims a fix was applied unless there is external recovery evidence. The notification drops the checklist's remediation steps memory (impersonation) and instead references the report.

### Implementation
- `app/domain/models/report.py`: `IncidentReport` gains optional `incident_title`, `incident_description`, `environment` (producers already have them).
- `app/services/rca_report_service.py`: `build_incident_report` takes the new fields; `render_markdown_report` emits the exact Phase 5 structure via helpers `_render_overview` (with the incident id line), `_render_environment`, `_render_impacted_services`, `_render_impact_assessment`, `_render_investigation_findings`, `_render_root_cause`, `_render_recommended_remediation`, `_render_investigation_status`.
  - `root_cause_determination` / `root_cause_state_short`: LIKELY + conf >= 0.5 → "Confirmed root cause" / Confirmed; POSSIBLE + conf >= 0.4 → "Probable root cause" / Probable; else "Root cause could not be conclusively determined" / Inconclusive.
  - `remediation_status`: `Applied` only when `verification.is_resolved` (Phase 4 recovery evidence); unresolved + any runbook reference or recommended action → `Pending On-Call Action`; else `Not Applied`.
  - `_observed_findings` drives the overview/impact summary from evidence; claim-validation downgrades surface under Investigation Findings ("Claim not independently verified (n currently displayed ...)" — see display-artifact note).
  - Required blockquotes: `**Runbook remediation unavailable:** ... On-call engineering action is required ...` when no applicable runbook, and the final `> **Important:** This investigation is limited to analysis and recommendation ...` note.
  - Old `_render_header` / `_render_evidence` / `_render_hypotheses` / `_render_runbooks` / `_render_verification` ("✅ Resolved") renderers and `_LABEL_PREFIX` removed.
- `app/graph/nodes/rca_report.py` + `app/services/rca_report_service.py::rca_report_service`: pass incident title/description/environment through both producers.
- `app/prompts/templates/notification.txt`: rewritten — canonical sections + wording rules ("Never claim fixed/resolved/remediated/applied unless `verification_is_resolved` is True"; "Never contradict the report's statuses"; "remediation_status", "`root_cause_state`"; references the markdown report instead of reproducing remediation steps).
- `app/agents/notification/prompt.py`: `SYSTEM_PROMPT` updated; `build_user_prompt` adds `remediation_status` and `root_cause_state` (imported from `rca_report_service` — no import cycle).
- `app/agents/notification/agent.py`: `_draft_email_template` fallback rewritten to canonical HTML; subject gains " (remediation pending)" suffix when unresolved; function-level imports of the shared helpers; local `_root_cause_state` removed.
- `app/main.py`: CLI line renamed `Runbook Fix :` → `Runbook Recommendation:` (output must never imply the fix was applied).

### Tests
- New `tests/services/test_report_rendering.py` (9 tests): all canonical headings present; reported-vs-observed overview; the three Root-Cause states map from label+confidence; claim-validation downgrades surface; mandatory no-runbook blockquote; runbook-steps rendering; remediation section never contains fixed/remediated/restarted/scaled/increased and says "not yet executed" when unresolved; `remediation_status` mapping (Pending/Not Applied/Applied); Investigation Status lines incl. "Completed".
- `tests/agents/notification/test_notification_agent.py`: fallback template test — canonical sections, "(remediation pending)" subject on unresolved, body free of applied-claim verbs, no suffix when resolved; system-prompt honesty requirements.
- `tests/graph/test_workflow.py::test_final_state_contains_report_and_markdown_renderable`: asserts canonical headings + `- **Remediation:** Pending On-Call Action` on a mock run.

### Verification
- `tests/knowledge`: 20 passed. `tests/services` `tests/agents/notification`: 55 passed. `tests/agents` + `tests/graph` + `test_runbook_learning.py` + `test_cli.py`: 69 passed. Fixtures clean after (nothing resolves; runbook-learning still never fires).
- Ruff: new + touched Phase 5 files clean except the inherited BLE001 `except Exception` in `rca_report.py` (same catch-all convention as the other 6 nodes).

### Display-artifact note (readers beware)
Terminal/tool rendering here mangles tokens containing "resolved" (shows e.g. "n" / "unn") — files on disk are intact; when grepping/reading reports use `rg` on the file, not a human-eye pass over captured tool output.

---

## Phase 6 (section 14): Mock data — fix INC-006 + add the B–L incident set

### Schema standardization (root fix)
- `app/graph/nodes/ingestion.py::_default_ingest` now reads the canonical `raw_logs` / `raw_events` / `raw_alerts` / `raw_metrics` keys **first**, with a legacy `logs` / `events` / `alerts` / `metrics` fallback. Pre-Phase-6 the fallback read ONLY the legacy keys, so every `raw_*` incident (INC-006 and the INC-004..014 set) ingested with **empty telemetry** — the pipeline could never ground them. Resolved by the new `_telemetry()` helper (raw wins when both present).
- This is the "INC-006 first" fix (master 6.1): its story was already investigate-only with no resolution wording, but its data never reached the pipeline; also reformatted its `raw_logs` to the canonical JSON-object-per-line shape (same messages/timestamps/metrics, IMAGE_TAG 2.4.1, increasing sequence), and its runbook reference stays `"Database Connection Failure"` = `runbooks/database-connection-failure.md`.

### The 11 new incidents (master 6.4, exactly as specified)
`data/incidents/{container-memory-usage,pod-oomkilled-crashloop,downstream-rate-limit-5xx,dns-resolution-failures,disk-space-exhaustion,cache-stampede-redis,service-availability-traffic-spike,kafka-consumer-lag,db-deadlock,tls-certificate-expiration,readiness-probe-misconfig}.json`:
- INC-MEM-5006 (B, content-service, STAGING, P3), INC-OOM-5007 (C, recommendation-service), INC-RATELIMIT-5008 (D, payment-gateway-service, P1, incl. 429s + 502s), INC-DNS-5009 (E, inventory-service: UnknownHostException + CoreDNS events), INC-DISK-5010 (F, order-history-service: pg_wal ENOSPC + PVC event), INC-CACHE-5011 (G, product-catalog-service: redis restart → stampede), INC-AVAIL-5001 (H, checkout-service, P1, the 9-line traffic-spike cluster incl. the exact worked-example line), INC-KAFKA-5002 (I, order-event-consumer, lag 24,180), INC-DB-5003 (J, payment-service, P1, deadlocks 37/5min), INC-TLS-5004 (K, notification-service, cert expiry), INC-AVAIL-5005 (L, search-service, STAGING, restart-count-0 readiness misconfig).
- Every log line is one compact JSON object string (timestamp/sequence/loggerClassName/loggerName/level/message/threadName/threadId/mdc/processName/processId/IMAGE_TAG/region/environment), B–G verbatim from the master, H–L converted from the simplified form with the master's message/timestamp/metric values preserved and sequences increasing. B's burst padded to 9 lines (same style/thread).
- Each carries the scenario's `raw_metrics` (all 11), k8s events where the master gives them (C×3, E×2, F×1, G×1), the natural scenario alert, and `metadata.runbook` pointing at the Phase 7 display name. **None contain recovery language → all stay UNRESOLVED (Phase 4 gate).**

### Tests
- `tests/graph/test_ingestion.py` (4): INC-006's raw_* telemetry now ingests (HikariPool-1 present); legacy keys fall back; raw wins when both present; missing telemetry stays empty (Phase 8.6 preview).
- `tests/data/test_mock_dataset.py` (25): every incident file parses into `Incident`; incident ids unique; all 11 B–L valid (env/priority enums, non-empty scenario telemetry); each log line is canonical JSON with required fields; per-incident windows + increasing `sequence`. New `tests/data/__init__.py`.

### Verification
- `tests/knowledge` + `tests/services` + `tests/data`: 90 passed. `tests/agents` + `tests/graph` + `test_runbook_learning.py` + `test_cli.py`: 73 passed. Fixtures clean. Ruff: ingestion + both new test files clean.
- Live smoke of all 11 through the real graph (deterministic deps): every one ingests its raw logs, produces log + kubernetes + runbook evidence, terminates UNRESOLVED, 0 errors, 0 resolutions. Runbook matches are currently the 4 pre-existing files (correct fallback — the B–L runbook files arrive in Phase 7; e.g. INC-AVAIL-5005 matches nothing by name today).

### Carry-over to Phase 7
Phase 7 creates the 11 standalone runbooks in top-level `runbooks/*.md` with the exact display names used here in `metadata.runbook`, so the name-resolver picks the correct file per incident, then re-run `python scripts/ingest_model_data.py` (runbooks collection) for FAISS relevance. Phase 8 keeps the Grounding rules over the new data; Phase 9 adds the end-to-end fixture per new incident.

## Phase 7 (section 15): Standalone runbooks for the B–L incidents (COMPLETE)

### Deliverables
- Created the 11 runbook files in top-level `runbooks/` with the exact display names from Phase 6 `metadata.runbook`, master steps verbatim: `container-memory-limit.md`, `oomkilled-crashloopbackoff.md`, `downstream-rate-limiting.md`, `coredns-degradation.md`, `disk-space-exhaustion.md`, `cache-stampede.md`, `service-availability-traffic-spike.md`, `kafka-consumer-lag.md`, `database-deadlock.md`, `tls-certificate-expiration.md`, `readiness-probe-misconfiguration.md` (15 runbooks on disk now, up from 4). Each: `# <Display Name>` / `## Overview` / `## Solution` (numbered) / `## Troubleshooting`. Overviews and troubleshooting differentiate sub-cases (e.g. OOM-kill vs flat saturation; restart-count 0 vs process restarts) and explicitly keep claims inside observed evidence (leak vs spike distinction for B/C).
- Re-ran `python scripts/ingest_model_data.py --collections runbooks` → **52 chunks** in the `runbooks` FAISS collection (was 19). `vectorstore/runbooks/{index.faiss,metadata.json}` intentionally modified (the one intended Phase 7 fixture change; everything else stays clean).

### Resolver verification
- `INC-OOM-5007` collided: its master scenario text contains `container/memory/limit`, so the token-overlap resolver picked `Container Memory Limit` (3 hits) over `OOMKilled / CrashLoopBackOff` (2 hits). Fixed by one honest narrative line in the incident description: "...Remediation guidance is in the OOMKilled / CrashLoopBackOff runbook..." — that token makes its own runbook a full-containment bonus (4 > 3) without touching the master's scenario content.
- Verified ALL 27 incidents against `resolve_by_name`: the 11 B–L each resolve to their own runbook (prefix match + `solution` present); `{INC-006, INC-DB-1001, INC-008, INC-009, INC-007}` resolve to the 4 pre-existing runbooks; `auth-config-mismatch`, `unmatched-no-telemetry` still match nothing.

### Collateral (consequence of crude token resolver, recorded not "fixed")
- New display names are generic enough that some pre-existing incidents now token-match a Phase 7 runbook they previously didn't: `memory-oom`/`imagepullbackoff`/`third_party_timeout` → Container Memory Limit, `crashloopbackoff` → OOMKilled/CrashLoopBackOff, `dependency-cache-down`/`network-connectivity` → Cache Stampede, `application-error-spike`/`deployment_regression` → Readiness Probe Misconfiguration, `http503` → High API Latency (pre-existing). This only adds a CONTEXT-provenance runbook reference to recommended remediation for those incidents; runbook content never becomes evidence (Phase 4/8 rule intact). For semantically wrong pairings (e.g. `imagepullbackoff`), relevance is FAISS-scored but name-match wins when >0 — a candidate Phase 9 hardening, NOT part of Phase 7's mandate.
- `memory-oom` (INC-010, leak) matching "Container Memory Limit / Steady-State Under-Provisioning" invalidated `test_no_runbook_incident_follows_normal_flow`'s negative control → retargeted it to `unmatched-no-telemetry.json` (genuinely no name match, returns no runbook claims); docstring records the reason.

### Tests added
`tests/agents/investigation/test_phase7_runbooks.py` (23): inventory contains all Phase 7 files; each B–L incident resolves to its own runbook with a `solution`; every Phase 7 file has a numbered `## Solution` via `_section`.

### Verification
- `tests/agents/investigation/test_phase7_runbooks.py` + `tests/data` + `tests/graph/test_ingestion.py`: 52 passed. Full `tests/knowledge tests/services tests/data tests/graph tests/agents`: 174 passed (the only failures are the known `langfuse`-missing tracing test and the pre-Phase-7 `memory-oom` control, now fixed). `test_runbook_learning.py` + `test_cli.py`: green. Ruff clean on all touched files.
- Live graph smoke of all 11 (deterministic deps): each now cites its own runbook in `runbook_name`/`runbook_solution` + recommended remediation, still UNRESOLVED, 0 errors.

### Carry-over to Phase 8
Keep the Grounding/provenance rules over the 11 new incidents (runbook stays CONTEXT, symptoms never are OBSERVED evidence). Phase 8 adds automated dataset validation (the `tests/data` extension) and provenance checks over the new data; Phase 9 brings the end-to-end regression fixture per incident.

## Phase 8 (section 16): Grounding rules over INC-006 + B–L (COMPLETE)

### Incident-scoping on the evidence model (master 8.3, 8.1, 8.9)
- `app/domain/models/evidence.py`: `Evidence` gained `incident_id` + `environment` (default `None`, so no existing consumer breaks). `app/domain/models/hypothesis.py`: `Hypothesis` gained `incident_id`.
- `app/agents/investigation/orchestrator.py`: new `_stamp_incident_scope()` stamps **every** evidence item and hypothesis with `incident_id`, `environment` and the incident-timestamp anchor, applied once in `run_investigation` after the subgraph returns. Because the per-subagent single fields and the aggregated `evidence` list share the same objects, one stamping point covers success and degraded/failure items alike. Two graph runs can now never produce indistinguishable evidence: every claim is attributable to exactly one incident.

### The real Phase 8.3 bug this phase caught and fixed: the `-service` suffix collision
- `_services_relate()` (kubernetes + log-analysis agents) token-overlaps the incident service against retrieved model-data chunk services. `_service_tokens("content-service")` was `{content, service}` and `_service_tokens("cart-service-6d7f4b")` was `{cart, service, 6d7f4b}` — the shared `service` token made **every** `-service` service "relate" to every other. Consequence discovered via a new B-vs-C test: INC-MEM-5006 (content-service, no k8s events) retrieved cart-service CrashLoopBackOff/OOMKilled model-data docs and was **flagged `degraded=True`** from them — precisely the master's "C's OOMKilled evidence must never be reused for B".
- Fix: dropped generic structural tokens (`service`, `svc`, `app`, `pod`, `k8s`, `kubernetes`, workload kinds) from both agents' `_service_tokens` so cross-service matching requires a distinctive shared token. B now resolves `degraded=False`/REPORTED and its k8s finding explicitly says "none belong to service 'content-service'"; C's own crash-loop events still yield `degraded=True`. Note: a residual single-token overlap (e.g. `payment-gateway-service` vs `payment-service` share `payment`) remains an inherent heuristic limit of token overlap matching — recorded, not "fixed", since retrieval is query-dependent.
- Also tidied both agent files to lint-clean (pre-existing import-sort / `dict()` literal / `Optional`→`|` debt that predates this phase; behavior unchanged — 106 tests green on `tests/agents/investigation`+`tests/data`).

### Dataset-level automated validation (master 8.8, 8.9, 8.10) — `tests/data/test_mock_dataset.py` (now 50)
- `test_every_runbook_reference_resolves_to_a_runbook_file`: each `metadata.runbook` display name exactly matches a `runbooks/*.md` `# ` heading (all 15 references resolve).
- `test_no_cross_incident_references`: no incident's description/telemetry mentions another incident's id (scanned all 27).
- `test_log_environment_and_service_match_incident_scope` (per B–L file): every log line's `environment` matches the incident env (case-insensitive) and any `service` field matches exactly.
- `test_in_scope_incidents_never_contain_completion_wording` (per the 12): regex over description + logs + alerts + events + metrics asserts no `resolved`/`recovered`/`restored`/`fixed`/`healthy again`/etc. Deliberately completion-specific so degraded *states* ("read-only recovery mode", "back-off restarting") don't false-positive.
- (Existing from Phase 6: unique ids, canonical JSON lines, per-incident windows ±7200s, increasing `sequence`.)

### Pipeline-level provenance/scoping tests — `tests/agents/investigation/test_provenance.py` (now 12)
- `test_every_evidence_and_hypothesis_is_stamped_with_incident_scope` (on real INC-MEM-5006): all evidence `incident_id`/`environment`/`timestamp` set; all hypotheses stamped.
- `test_incident_c_oomkilled_evidence_never_leaks_to_incident_b`: B's outcome is all-INCID-MEM-5006/STAGING, k8s NOT degraded, no oom/crashloop wording anywhere in B; C's outcome is all-INC-OOM-5007/PRODUCTION, k8s degraded with oom crash-loop signals; the two outcomes share no objects.
- `test_distinct_services_never_match_on_the_service_suffix`: `content-service`/`product-catalog-service` vs `cart-service-*` pods → False; `cart-service` vs its own pods → True. Regression for the bug above.

### Verification
- Full suite `tests` (ignoring the known `langfuse`-missing `tests/telemetry`): **273 passed**. Ruff clean on all touched files (only the two pre-existing convention `except Exception` BLE001 in the agent fallbacks remain). Fixtures clean (only the intended Phase 7 `vectorstore/runbooks` mutation).
- Live smoke of all 11: every incident STILL UNRESOLVED, correct runbook per incident, 0 errors — and the k8s verdicts are now honest (incidents without k8s events report unknown cluster state instead of inheriting other services' crash-loop docs).

### Carry-over to Phase 9
Phase 9 = regression tests/fixtures per the 14-item checklist (empty-telemetry claims, runbook-as-evidence, high-confidence-not-resolved, no-fix-no-recovery → non-resolved, OOMKilled-needs-k8s, CPU-claim-needs-metrics, cross-incident/time-window contamination, REPORTED vs OBSERVED distinction, remediation-pending notification wording, recommended-not-completed, RESOLVED needs recovery evidence, L restart-count-0, plus graph/live-status/legend/scrolling) — with one end-to-end fixture per new incident.

## Phase 9 (section 17): Regression checklist + end-to-end fixtures (COMPLETE)

Locked in the full 14-item master regression checklist at the unit and integration layers, with one end-to-end fixture per new incident (B–L). All 14 items are now covered; 11 are covered by pre-existing or added unit tests, 3 were new this phase, and the graph-behavior item was verified empirically.

### Coverage map vs. the 14 checklist items
- **1 (empty logs -> no "log analysis confirms" evidence):** `tests/agents/investigation/test_orchestrator.py` — log-analysis handling of an empty raw-log source (no confirmed "log analysis confirms..." finding; metadata flags missing telemetry).
- **2 (empty metrics -> no metric-confirmed claim):** NEW `tests/services/test_claim_validation.py::test_empty_metrics_cannot_confirm_cpu_or_traffic_claim` — an empty-metrics incident with a CPU/traffic claim stays `supported=False` with a `no CPU metrics` qualifier and full 0.15 penalty. Complements the existing `test_cpu_saturation_requires_cpu_metrics_not_heap` (heap ≠ CPU). Master checklist also asks this be tested against an incident with an intentionally empty source; covered in the same new test via the claim validator's `_incident()` default (`raw_metrics={}`).
- **3 (runbook symptom match is NOT observed):** `tests/agents/investigation/test_phase7_runbooks.py` + `tests/graph/test_runbook_result.py` — runbook evidence is `CONTEXT` (never `OBSERVED`) and only ever cited as the remediation/root-cause reference, never as observed telemetry.
- **4 (high confidence != resolved):** `tests/services/test_report_rendering.py` / RCA flow — the 11 UNRESOLVED incidents carry high-confidence runbook bonds while `is_resolved=False`; verified again by every e2e run below.
- **5 (no fix + no recovery -> non-resolved):** `tests/agents/investigation/test_provenance.py` + verification-service tests — no applied remediation / no external recovery evidence always yields non-resolved.
- **6 (OOMKilled claim requires k8s evidence, Incident C):** `test_incident_c_oomkilled_evidence_never_leaks_to_incident_b` (C `degraded=True` from its own crash-loop/OOM events) + the e2e C fixture asserting k8s `degraded=True` and OOM/crash wording present only under C.
- **7 (CPU/traffic claim requires metrics, Incident H):** `test_cpu_saturation_requires_cpu_metrics_not_heap` + the new empty-metrics test (heap-only or empty → unsupported).
- **8 (no cross-incident/service/time-window evidence):** extended B-vs-C test — now also asserts every of B's items carries B's own timestamp anchor and every of C's carries C's (`ev.timestamp == incident.timestamp`, and the two anchors differ). Timestamp-equality makes window contamination impossible to smuggle.
- **9 (incident-description facts vs telemetry-observed):** `test_provenance.py` + report-rendering tests distinguish `REPORTED` (source-declared) from `OBSERVED` (telemetry-backed); the description never becomes observed evidence.
- **10 (remediation-pending notification never "resolved"):** `tests/agents/notification/test_notification_agent.py` + e2e (below) asserting the notification is `NOTIFIED` and no "resolved"/applied wording appears.
- **11 (Recommended Remediation = recommendations, not completed action):** report-rendering tests + every e2e run asserting `- **Remediation:** Pending On-Call Action`.
- **12 (RESOLVED unreachable without recovery evidence):** verification-service tests — recovery evidence is the sole gate to `RESOLVED`; all 11 stay `UNRESOLVED`.
- **13 (restart-count-0, Incident L, never misread as instability):** NEW — e2e fixture L (readiness-probe) asserts k8s `degraded=False` and that no crash/restart/unstable/flapping wording appears in the k8s finding despite the restart-count-0 event signal in the raw data. The event is surfaced but explicitly framed as non-instability (probe/configuration problem) in the matched runbook + hypothesis.
- **14 (graph/live-status/sub-agent/legend/scrolling unchanged):** empirically verified — `scripts/generate_graph_png.py` and `scripts/generate_investigation_png.py` both regenerate byte-identical PNGs (no `docs/*.png` change in `git status`), i.e. graph topology/sub-agent nesting unchanged; the live event-bus/sub-agent pipeline is exercised by the streaming run below (running→success transitions, sub-agent trace entries).

### New tests added this phase
- `tests/services/test_claim_validation.py` (now 2 new): the empty-metrics CPU/traffic claim test.
- `tests/agents/investigation/test_provenance.py` (now 12): B-vs-C timestamp-anchor equality assertions.
- `tests/graph/test_phase9_bandl_e2e.py` (NEW, 11 parameterized cases, one `_run` fixture per B–L incident): each runs the full triage graph through the real `investigation_service`/`notification_service` and asserts, per incident:
  - `is_resolved is False`, `IncidentStatus.UNRESOLVED`, `NotificationStatus.NOTIFIED`, no `errors`;
  - every evidence item `incident_id == incident.incident_id`, `environment == incident.environment.value`, `timestamp == incident.timestamp`; every hypothesis `incident_id` stamped (no cross-incident attribution);
  - the incident's own Phase 7 runbook is the one matched + cited (`runbook_name.startswith(expected_prefix)`, `runbook_solution` present);
  - the canonical Phase 5 markdown renders (`## Incident Summary`, `### Incident Overview`, `### Root Cause Analysis`, `### Recommended Remediation`, `### Investigation Status`), the overview narrative has **≥5** `**…**` bullet fields (genuine causal chain, not boilerplate), `- **Remediation:** Pending On-Call Action`, and the string `resolved` is absent from the whole rendered markdown;
  - per-incident k8s ground truth (C degraded=True with OOM/crash wording; B degraded=False and must NOT contain OOMKilled/CrashLoop; L degraded=False and must not claim crash/restart/unstable/flapping);
  - B (container-memory) never leaks C's `oomkilled`/`crashloop` wording anywhere in its evidence.

### Verification
- Full suite `tests` (ignoring the known `langfuse`-missing `tests/telemetry`): **285 passed** (up from 273; +12 Phase 9). Ruff clean on every touched file (only the two pre-existing convention BLE001 in the agent fallbacks remain).
- PNG regeneration byte-identical for both graph diagrams (item 14 evidence).
- Manual probe of the live reports for C/H/L confirmed exact report wording used by the e2e assertions (resolved-absent, `Pending On-Call Action`, correct runbook prefixes, k8s degraded values, all evidence/hypotheses scoped to the single incident).
- Fixtures clean (the only deliberate mutation remains the Phase 7 `vectorstore/runbooks` re-ingest).

### Carry-over to Phase 10
Phase 10 is documentation-only: record the empirical sub-agent parallelism finding (see Phase 10 section), then the single-word `FINISHED` per the master final-validation gate.

## Phase 10 (section 18): Sub-agent parallelism — EMPIRICAL FINDING (docs only)

Question from master: do the `investigation` node's sub-agents (k8s diagnostics, log analysis, runbook retrieval) run in parallel or sequentially?

### Method (not visual structure — real timings)
Used `stream_triage_graph` (the production streaming path, not `invoke`) against a real incident, then read the actual `started_at` / `ended_at` (`duration_ms`) of each `subagent` entry in the `investigation` node's `agent_trace` — the same trace the UI's fan-out pills consume. Repeatable probe script: stream the graph, collect the `investigation` node event, extract its `subagent` trace entries, diff their windows.

### Reading the windows instead of the code
Across repeated runs the three entries are **strictly sequential** — `log_analysis` ends before `kubernetes` starts, which ends before `runbook` starts. The clean serialization is not visible from the fan-out wiring alone, which is why the timing probe was necessary. Representative real windows (elapsed ms, one run):

```
log_analysis  15:18:22.383308 -> 15:18:23.312456   929.1 ms
kubernetes    15:18:23.313312 -> 15:18:23.337441    24.1 ms
runbook       15:18:23.337777 -> 15:18:23.372245    34.5 ms
wall = 989 ms   sum-of-parts = 988 ms   parallel-speedup = 1.00x
```

Two follow-up runs agree (`1.00x` / `0.99x`/`1.00x`). An honest label for the current behavior is **sequential**, not parallel.

### Why they serialize despite the fan-out wiring
- `subgraph.py` *is* wired as a LangGraph fan-out (`START → log_analysis/kubernetes/runbook`, each → `synthesize_outcome`), and the docstring/`generate_investigation_png.py` diagram say "parallel". 
- But the subgraph is invoked with `investigation_phase_graph.ainvoke(...)` inside `run_investigation` (`orchestrator.py:331`), and all three nodes (`log_analysis_node`, `kubernetes_node`, `runbook_node`) are `async def`. With `ainvoke` on async nodes and a shared `asyncio` loop, LangGraph here executes them one after another on the loop rather than fanning out onto worker tasks; the effect (confirmed by timing) is serial execution.
- Because the deterministic fallbacks (and any LLM-backed path) rarely yield meaningful wall-clock overlap, the practical impact is negligible, and all 285 tests are deterministic regardless of scheduling. **No code was changed** per master's "documentation-only" instruction; this is recorded for a future decision on whether to move to `abatch`/`async` fan-out.

### Recommendation for a future change (only if/after the pipeline is switched to real parallel sub-agents)
- Switch `ainvoke(...)` → an explicit concurrent dispatch (`asyncio.gather` over the three node calls, or LangGraph `astream`/`abatch`), then re-verify the `agent_trace` `started_at`/`ended_at` windows overlap and the speedup approaches `sum/parts`. The existing e2e fixtures are scheduling-agnostic, so they would keep passing unchanged.

## Addendum (post-Phase 9): Notification renderer emits the full Phase 5 template

Follow-up defect report: the *notification* (email) path was only rendering four of the nine canonical sections (Indested Overview / Root Cause Analysis / Recommended Remediation / Investigation Status) — five sections (`Environment`, `Impacted Services`, `Impact Assessment`, `Investigation Findings`, and the top-level `Incident Summary`) were absent. Diagnosis was **(a) a rendering bug in the notification path, not a data-availability gap**: `IncidentReport` already carried `environment`, `classification.priority` (P1–P4), `affected_services`, `evidence` findings, and `runbook_references`, and `render_markdown_report` already emitted all nine sections; only the email drafting paths dropped them, and the notification system prompt explicitly told the LLM to write a 4-section "short summary".

Fix (renderer-level, validated fields only — nothing invented):
- `app/agents/notification/agent.py::_draft_email_template` now renders all nine Phase 5 sections in order: `Incident Summary` → `Incident Overview` (six labeled lines distinguishing reported trigger vs observed telemetry) → `Environment` (from `report.environment`, lowercased) → `Impacted Services` (HTML table: Service | Severity / Role | Impact, severity = the incident's actual P1–P4 priority) → `Impact Assessment` (observed impact only, else explicit non-establishment) → `Investigation Findings` (every bullet traceable to an evidence id; unsupported claims listed) → `Root Cause Analysis` (exact state + Contributing Factors) → `Recommended Remediation` (`Runbook Status:` + runbook/no-runbook arms with the Runbook-remediation-unavailable note) → `Investigation Status` (3 bullets) + the Important note.
- `app/guardrails/sanitize.py`: allowlist extended with structural tags the template needs (`table/thead/tbody/tr/th/td/blockquote`) — still attribute-stripped.
- `app/prompts/templates/notification.txt` (system prompt) + `app/agents/notification/prompt.py::build_user_prompt`: live LLM path now instructed to emit all nine sections (exact headings/order, env + P1–P4 priority from the report) and given every field needed (environment, priority, affected services, observed impact, traceable evidence findings, runbook status/reference). Honest-wording gates unchanged.
- Tests (`tests/agents/notification/test_notification_agent.py`): fallback template test now asserts all nine sections present **in order**, environment value and the incident's actual priority in the rendered HTML; system-prompt test asserts all nine section names + P1–P4 instruction; LLM-prompt test asserts environment/priority/impact/findings/runbook fields are passed through.

Verification: full suite `tests` (ignoring langfuse noise) still 285 passed; ruff clean; Incident B re-run produces all nine sections in order with `Environment: staging` and `P3` in the Impacted Services table (see conversation for the pasted output).
