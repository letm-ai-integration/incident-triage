# LangGraph Integration Specification — `app/graph/`

**Scope of this document:** This is a standalone instruction file for a coding
agent (human or AI) that needs to build, extend, or modify the LangGraph
integration for the `ai-incident-triage` project **without needing to
understand the entire codebase first.**

**Hard scope boundary:** All code you write or modify lives inside
`app/graph/`. That means:

```
app/graph/
├── workflow.py
├── state.py
├── router.py
├── builder.py
└── nodes/
    ├── ingestion.py
    ├── classification.py
    ├── investigation.py
    ├── investigation_summary.py
    ├── rca_report.py
    ├── approval.py
    ├── verification.py
    └── notification.py
```

You do **not** create new top-level folders, new agent frameworks, or a
second graph abstraction. Everything the graph layer needs — models, enums,
agents, services, tools, guardrails, LLM access, logging, tracing — already
exists elsewhere in the project. Your job is to **wire those existing pieces
together as LangGraph nodes and edges**, not to reinvent them.

---

## 0. Mandatory First Step — Read Before You Write

Before writing or editing **any** code in `app/graph/`, you must read, in
this order:

1. **`app/domain/enums/`** — `priority.py`, `incident_type.py`,
   `environment.py`, `team.py`, `status.py`.
   These enums define every categorical value that can appear in graph
   state or routing decisions (e.g. incident priority, status transitions,
   team ownership). **Never invent a new string literal or a new enum for a
   concept that already has one here.** If routing logic needs a new status
   value, check `status.py` first — extend it there, not in the graph
   layer.

2. **`app/domain/models/`** — `incident.py`, `classification.py`,
   `evidence.py`, `hypothesis.py`, `root_cause.py`, `approval.py`,
   `verification.py`, `report.py`.
   These are the domain objects that flow through the pipeline
   (Incident → Classification → Evidence/Hypothesis → RootCause → Approval →
   Verification → Report). Graph state fields should reference or wrap these
   models, not duplicate their fields.

3. **`app/schemas/graph_state.py`** — this is very likely the existing
   canonical definition (or partial definition) of graph state used
   elsewhere in the app (e.g. in API request/response schemas). Check
   whether the shape of state you need already exists here before defining
   anything new in `app/graph/state.py`.

4. **`app/graph/state.py`** itself — read what state fields already exist.
   If the field you need is already there, reuse it. If it's *close but not
   quite right*, prefer extending/adjusting it over creating a parallel
   field. Only add a new field if no existing field, model, or enum
   captures the concept.

5. **`app/agents/`** for the agent(s) relevant to your task (e.g.
   `classification/agent.py`, `investigation/orchestrator.py`,
   `investigation/log_analysis/agent.py`, `rca_report/agent.py`,
   `notification/agent.py`) and `app/agents/base.py` for the shared agent
   interface/contract.

6. **`app/services/`** for the service(s) that already wrap business logic
   for this step (e.g. `classification_service.py`,
   `investigation_service.py`, `hypothesis_service.py`,
   `rca_report_service.py`, `approval_service.py`, `verification_service.py`,
   `notification_service.py`). Nodes should call into services/agents, not
   reimplement their logic inline.

7. **`app/dependencies.py`** and **`app/config.py`** — how configuration and
   dependencies (LLM clients, repositories, tools) are currently constructed
   and injected. Graph nodes must obtain dependencies the same way the rest
   of the app does — do not hand-roll a new DI mechanism.

8. **`app/utils/logger.py`** and **`app/telemetry/`** (`langsmith.py`,
   `tracing.py`, `metrics.py`) — how logging and observability are already
   done. Nodes must log and trace the same way, not introduce a second
   logging convention.

9. **`app/guardrails/`** (`validator.py`, `safety_guard.py`,
   `prompt_injection.py`, `pii_guard.py`, `domain_guard.py`) — if a node
   produces or consumes LLM output, check whether guardrail validation
   already applies at the service/agent layer before adding your own
   validation in the node.

**Rule of thumb:** if you find yourself about to define a new Pydantic
model, a new enum, a new state field, or a new logging pattern — stop and
grep the codebase first. Only proceed with something new if you've
confirmed nothing equivalent already exists. If something exists but is
almost right, update it in place rather than creating a duplicate next to
it — but only within the files you're allowed to touch (see §7, Rules).

---

## 1. Architecture

### 1.1 Where graph code lives

| File | Responsibility |
|---|---|
| `app/graph/state.py` | The `TypedDict`/Pydantic graph state definition(s) that flow through the graph. Built on top of `app/domain/models/*` and `app/schemas/graph_state.py` — not a competing definition. |
| `app/graph/builder.py` | The composition layer: `create_graph()`, `add_node()`, `add_edge()`, `add_conditional_edge()`, `compile_graph()`. This is the **only** place `StateGraph(...)` should be instantiated directly. |
| `app/graph/router.py` | Pure routing/decision functions used by conditional edges (e.g. "should this incident go to approval or auto-resolve?"). No I/O, no side effects — routers only read state and return a destination node name. |
| `app/graph/workflow.py` | The actual incident-triage workflow definition: calls `builder.py` functions to assemble the production graph from `nodes/*`, in the correct order, and exposes the compiled graph for `main.py`/API layer to invoke. |
| `app/graph/nodes/*.py` | One file per pipeline stage. Each node is a thin adapter: it pulls what it needs from state, calls the relevant agent/service, and writes results back into state. Nodes contain **no business logic** — that lives in `app/agents/` and `app/services/`. |

### 1.2 State

Graph state is a single object shared across the whole workflow (ingestion →
classification → investigation → investigation summary → RCA report →
approval → verification → notification). It is built from existing domain
models, e.g.:

- `incident: Incident` (from `domain/models/incident.py`)
- `classification: Classification | None`
- `evidence: list[Evidence]`
- `hypotheses: list[Hypothesis]`
- `root_cause: RootCause | None`
- `approval: Approval | None`
- `verification: Verification | None`
- `report: Report | None`
- plus bookkeeping fields (status, errors, trace/run id) that should reuse
  `domain/enums/status.py` and whatever run-id/telemetry convention already
  exists in `app/telemetry/`.

**Do not shadow domain models with new inline field definitions.** Reference
them directly.

### 1.3 Nodes and edges

- A **node** = a Python callable `(state: GraphState, **deps) -> GraphState`
  (or a partial-state update dict, depending on what `state.py` already
  establishes as the return convention — check it, don't assume).
- An **edge** = a normal, unconditional transition from one node to another.
- A **conditional edge** = a transition governed by a routing function in
  `router.py` that inspects state (e.g. `classification.priority`,
  `verification.status`) and returns the name of the next node.

### 1.4 Conditional routing

Routing decisions must be based on the existing enums
(`domain/enums/priority.py`, `status.py`, `team.py`, etc.), never on raw
strings. Example decision points already implied by the node list:

- After `classification`: route by `Priority` / `IncidentType` to decide
  whether `investigation` runs the full multi-agent investigation
  (log analysis + runbook + kubernetes) or a lighter path.
- After `investigation_summary` → `rca_report`: always sequential (no
  branching needed unless evidence says otherwise).
- After `rca_report`: route to `approval` if policy requires human sign-off
  (check `rules/ownership.py` / `rules/confidence.py` for the existing
  threshold logic — reuse it, don't reimplement it in `router.py`), else
  skip straight to `verification`.
- After `approval`: route to `verification` if approved, or to
  `notification` (rejection path) if not.
- After `verification`: route to `notification` on completion, or back to
  `investigation` if verification fails (retry loop) — only if the existing
  domain/service layer already supports this retry concept; do not invent a
  retry policy that doesn't exist elsewhere in the app.

### 1.5 Graph composition

`builder.py` must support:

- Registering nodes from independently developed modules (e.g. someone adds
  a new `nodes/cost_analysis.py` without touching `workflow.py`'s internals
  beyond one `add_node` + `add_edge` call).
- Composing sub-graphs — e.g. the `investigation` stage may itself be a
  small internal graph (log_analysis, runbook, kubernetes agents running in
  parallel/sequence) compiled separately and mounted as a single node in the
  top-level workflow, if `agents/investigation/orchestrator.py` doesn't
  already handle that fan-out itself. **Check the orchestrator first** —
  if it already coordinates the three investigation agents, the graph layer
  should call the orchestrator as one node, not re-implement the fan-out.

---

## 2. Creating a Node — Exact Instructions

1. **Where to put it:** `app/graph/nodes/<stage_name>.py`. One node per
   pipeline stage matching the existing file list. Only add a new file here
   if you are adding a genuinely new pipeline stage — not for helper logic
   (helpers belong in `services/` or `utils/`).

2. **Naming/interface:** Function name = `<stage_name>_node`, e.g.
   `def classification_node(state: GraphState, **deps) -> GraphState:`.
   Match whatever signature convention `state.py`/`builder.py` already
   establishes (check for an existing node file first — `ingestion.py` and
   `classification.py` already exist; mirror their signature exactly for
   consistency).

3. **State input/output:** Read only the state fields you need. Return only
   the fields you changed (or the full state, matching whatever convention
   the existing nodes use — verify, don't assume). Never add a new field to
   the return value that isn't declared in `state.py`.

4. **Dependency access:** Obtain agents/services/tools/LLM clients the same
   way `app/dependencies.py` already provides them elsewhere (e.g. via a
   dependency container, factory function, or constructor injection —
   check `dependencies.py` and mirror it). Do not import and instantiate
   an LLM provider directly inside a node.

5. **Error handling:** Reuse whatever error/exception convention already
   exists (check `services/*` and `guardrails/validator.py` for how errors
   are surfaced). A node should catch expected domain errors, record them
   into the state's error/status field (per `domain/enums/status.py`), and
   let the graph route to an appropriate failure/notification path rather
   than raising uncaught exceptions that crash the whole graph run.

6. **Registration/export:** The node function must be importable from
   `app/graph/nodes/__init__.py` (create this if it doesn't exist, matching
   Python package conventions) and registered in `workflow.py` via
   `builder.add_node(graph, "classification", classification_node)`.

7. **Testing:** Add a test alongside the project's existing test
   conventions (check for a `tests/` directory or inline test setup already
   used for `services/`/`agents/` — mirror it). At minimum: test that the
   node correctly maps an existing service/agent call into a state update,
   using mocked dependencies.

---

## 3. Adding Edges

- **`add_edge(graph, "node_a", "node_b")`** — direct, unconditional
  transition. Use for strictly sequential stages (e.g.
  `ingestion → classification`, `investigation → investigation_summary`,
  `investigation_summary → rca_report`).

- **Conditional edges** — use `add_conditional_edge(graph, "node_a",
  router_fn, {"outcome_1": "node_b", "outcome_2": "node_c"})`. The
  `router_fn` lives in `router.py`, takes `state` only, and returns a
  string key present in the mapping. Router functions must be pure
  (no I/O, no calls to services/LLMs) — they only inspect state fields
  that were already computed by a prior node.

- **START/END:** Use LangGraph's `START` to connect the entry node
  (`ingestion`) and `END` from every terminal path (`notification` is the
  natural terminal node for both success and rejection paths, based on the
  node list — verify against `workflow.py` once it exists).

- **Validation and naming rules:**
  - Node names are the `snake_case` stage name matching the filename in
    `nodes/` (e.g. `"rca_report"`, not `"RCAReportNode"`).
  - `add_node`/`add_edge` must reject duplicate node names and edges that
    reference an unregistered node — raise a clear `GraphBuildError` (define
    once in `builder.py`, reuse everywhere) rather than letting LangGraph's
    raw exception surface.
  - No two conditional edges may originate from the same node with
    overlapping outcome keys.

---

## 4. Integrating an Agent Into the Graph

1. **Locate or create the agent** in `app/agents/` — check first, most
   agents already exist (`classification`, `investigation/*`, `rca_report`,
   `notification`). Only build a new agent if the task genuinely needs one
   the project doesn't have.

2. **Create its graph node** in `app/graph/nodes/<matching_stage>.py`,
   calling the agent (typically via its owning `services/*.py` wrapper, if
   one exists — prefer calling the service over the agent directly if the
   service already adds validation/guardrails/logging).

3. **Register/export** the node from `nodes/__init__.py`.

4. **Add it to a graph** with `builder.add_node(graph, "<stage>", <node_fn>)`
   inside `workflow.py` (or a feature-specific graph file if composing a
   separate sub-graph).

5. **Connect it** with `add_edge`/`add_conditional_edge` to its upstream and
   downstream neighbors, matching the pipeline order implied by the
   `nodes/` file list.

6. **Verify state compatibility:** confirm every state field the agent/node
   reads is produced by an upstream node, and every field it writes is
   declared in `state.py`. Do not add ad hoc fields to satisfy one agent —
   extend `state.py` properly (after confirming §0 that no existing
   model/field already covers it).

7. **Compile and test:** run `builder.compile_graph(graph)` and add/execute
   a test that runs the graph (or the relevant subgraph) end-to-end with
   mocked agent/service responses, asserting the final state shape.

---

## 5. Extending / Creating Graphs

- **Extending the existing workflow:** add a node + edges in
  `workflow.py`, following §2–§3. Do not touch other nodes' internals.

- **Creating a new graph:** only if the task is a genuinely separate
  workflow (not a variant of incident triage) — e.g. a maintenance or
  batch-reprocessing graph. Create it as a new module under `app/graph/`
  (e.g. `app/graph/reprocessing_workflow.py`), but **reuse** `state.py`,
  `builder.py`, and existing nodes wherever the stages overlap. Do not
  duplicate `builder.py`'s `add_node`/`add_edge` logic.

- **Composing independently developed components:** a sub-graph (e.g. the
  investigation fan-out across log_analysis/runbook/kubernetes agents) is
  compiled independently and mounted into the parent graph as a single node
  via `builder.add_node(graph, "investigation", compiled_subgraph_as_node)`.
  This lets teams build/test their slice in isolation before it's wired
  into the main workflow.

---

## 6. Debugging Guide

| Symptom | Likely cause | Where to look |
|---|---|---|
| `GraphBuildError: duplicate node` | Two modules registered the same node name | `workflow.py` registration order; check `nodes/__init__.py` exports for accidental double-registration |
| `GraphBuildError: unknown node in edge` | Edge references a node not yet added, or a typo in the node name string | Compare the string in `add_edge`/`add_conditional_edge` against the exact key used in `add_node` |
| State field `KeyError`/`AttributeError` | A node reads a field no upstream node produced, or `state.py` doesn't declare it | Trace the field back through `domain/models/` and `schemas/graph_state.py`; confirm the producing node runs earlier in the graph |
| Routing function always picks the same branch | Router is reading a field that hasn't been set yet, or is comparing against a raw string instead of the enum from `domain/enums/` | Check enum equality (`Status.APPROVED` vs `"approved"`); confirm the field was written by the immediately prior node |
| Graph compiles but a node's output is silently ignored | Node returns a dict/state object with a key that doesn't match the field name in `state.py` exactly | Check exact spelling/casing against `state.py` |
| Async node hangs or errors | Node mixes sync and async agent/service calls incorrectly | Confirm whether agents/services in `app/agents/` and `app/services/` are `async def` — nodes must `await` them, not wrap them in sync calls |
| Dependency not found inside a node | Node is instantiating a dependency itself instead of receiving it the way `dependencies.py` provides it elsewhere | Check `app/dependencies.py` for the injection pattern and mirror it |
| Guardrail/validation errors surfacing as raw exceptions | Node bypassed `guardrails/validator.py` and called an LLM-backed agent directly without the existing validation wrapper | Route the call through the same service the rest of the app uses, which already applies guardrails |
| Compilation failure with cyclic graph error | A conditional edge creates an unintended cycle (e.g. verification → investigation retry loop with no exit condition) | Confirm the router has a terminating condition and that `domain/enums/status.py` has a state that represents "give up"/"max retries" |

---

## 7. Rules for Coding Agents Working on This Codebase

You **must not**:

1. Create a second graph abstraction alongside `builder.py` (e.g. a
   different way of instantiating `StateGraph` elsewhere in the codebase).
2. Bypass the public `add_node`/`add_edge`/`add_conditional_edge` API to
   call LangGraph internals directly, unless `builder.py` genuinely cannot
   support the operation — and if so, extend `builder.py` itself rather
   than working around it in `workflow.py` or a node file.
3. Invent new state fields without first checking `app/graph/state.py`,
   `app/schemas/graph_state.py`, and `app/domain/models/*` for an existing
   equivalent.
4. Invent new categorical/status values without first checking
   `app/domain/enums/*` for an existing equivalent — extend the enum there
   if genuinely missing, rather than using raw strings in the graph layer.
5. Duplicate or casually rename an existing public node, agent, service, or
   state field "for clarity." If a rename is truly needed, do it in the
   owning file and update all call sites — don't create a second name next
   to the old one.
6. Change unrelated architecture outside `app/graph/` (and the narrow,
   explicitly-justified exception of extending an enum/model when nothing
   equivalent exists — and even then, edit the existing enum/model file in
   place rather than adding a parallel one).
7. Add new third-party dependencies to `pyproject.toml`/`requirements.txt`
   without explicit justification tied to a capability `langgraph` itself
   doesn't provide.
8. Silently change existing node/edge/behavior when asked to add something
   new — additive changes only unless the task explicitly asks for a
   behavior change.
9. Create node interfaces incompatible with the signature/return convention
   already established by the existing `nodes/*.py` files.

### Required workflow for every change

```
Inspect existing code (domain/enums, domain/models, schemas/graph_state.py,
graph/state.py, agents/, services/, dependencies.py, utils/logger.py,
telemetry/, guardrails/)
   → Understand graph/state architecture as it currently stands
   → Search for an existing node/agent/service/model/enum that already
     covers the need
   → If found: reuse it as-is, or update it in place if it's close but
     not quite right
   → If not found: create the smallest new node/state field/enum value
     needed, in the correct existing file/location
   → Register/export the node (nodes/__init__.py)
   → Add edges (builder.add_edge / add_conditional_edge) in workflow.py
   → Validate: run builder.compile_graph(graph) and confirm no
     GraphBuildError
   → Update tests
   → Run tests
   → Review: re-read the diff and confirm nothing outside app/graph/
     changed without explicit justification, and no duplicate
     abstraction was introduced
```

---

## 8. Examples (fill in once `builder.py`'s exact signatures are finalized)

1. **Simple node registration**
   ```python
   from app.graph.builder import create_graph, add_node
   from app.graph.nodes.ingestion import ingestion_node

   graph = create_graph(state_schema=GraphState)
   add_node(graph, "ingestion", ingestion_node)
   ```

2. **Node + edge**
   ```python
   add_node(graph, "classification", classification_node)
   add_edge(graph, "ingestion", "classification")
   ```

3. **Conditional edge**
   ```python
   from app.graph.router import route_after_classification

   add_conditional_edge(
       graph,
       "classification",
       route_after_classification,
       {
           "full_investigation": "investigation",
           "auto_resolve": "notification",
       },
   )
   ```

4. **Independent agent integration** (e.g. adding a new `cost_analysis`
   stage contributed by another team)
   ```python
   # app/graph/nodes/cost_analysis.py
   from app.agents.cost_analysis.agent import CostAnalysisAgent

   async def cost_analysis_node(state: GraphState, **deps) -> GraphState:
       agent = deps["cost_analysis_agent"]
       result = await agent.run(state.incident, state.evidence)
       state.cost_estimate = result
       return state
   ```
   ```python
   # workflow.py
   add_node(graph, "cost_analysis", cost_analysis_node)
   add_edge(graph, "investigation_summary", "cost_analysis")
   add_edge(graph, "cost_analysis", "rca_report")
   ```

5. **Composed graph** (mounting the investigation sub-graph as one node)
   ```python
   investigation_subgraph = build_investigation_subgraph()  # log_analysis + runbook + kubernetes
   compiled_investigation = compile_graph(investigation_subgraph)

   add_node(graph, "investigation", compiled_investigation)
   add_edge(graph, "classification", "investigation")
   add_edge(graph, "investigation", "investigation_summary")
   ```

> These examples use illustrative signatures. Once `builder.py` is
> implemented, replace them with the actual, verified public API and keep
> this file in sync — do not let the spec drift from the real code.

---

## 9. File Ownership Summary

| File | You may create it if missing | You may edit it | You must not touch |
|---|---|---|---|
| `graph/state.py` | ✅ if it doesn't exist yet | ✅ to extend, only after §0 check | — |
| `graph/builder.py` | ✅ if it doesn't exist yet | ✅ | — |
| `graph/router.py` | ✅ if it doesn't exist yet | ✅ | — |
| `graph/workflow.py` | ✅ if it doesn't exist yet | ✅ | — |
| `graph/nodes/*.py` | ✅ for new stages only | ✅ | — |
| `domain/enums/*`, `domain/models/*` | ❌ only edit, don't create new files for concepts that fit existing ones | ✅ only when §0 confirms nothing equivalent exists | Don't restructure existing enums/models beyond the needed addition |
| `agents/*`, `services/*`, `tools/*`, `llm/*`, `guardrails/*` | ❌ | ❌ (call into them, don't modify) | ✅ leave untouched unless the task explicitly requires an agent/service change |
| Everything else (`main.py`, `config.py`, `knowledge/`, `repositories/`, `rules/`, `telemetry/`, `prompts/`) | ❌ | ❌ | ✅ leave untouched |

---

## 10. Future Extensions (not in current scope)

Flagging where the graph layer could grow later, without building it now:

- **Persistence/checkpointing** — LangGraph checkpointers could back
  long-running incident investigations so they survive process restarts;
  would slot into `builder.py`'s `compile_graph` as an optional param.
- **Streaming** — streaming intermediate node output (e.g. partial RCA
  drafts) to the API layer for live UI updates.
- **Human-in-the-loop** — an explicit interrupt at the `approval` node
  already implied by the existing node list; could use LangGraph's
  interrupt/resume primitives instead of a synchronous approval call.
- **Subgraphs** — formalizing the investigation fan-out
  (log_analysis/runbook/kubernetes) as a reusable, independently testable
  subgraph, per §5.
- **Observability** — deeper integration with `app/telemetry/langsmith.py`
  and `tracing.py` for per-node latency/error dashboards.

Do not implement any of the above unless explicitly requested — they are
listed here only so a future task knows where the natural extension points
are.
