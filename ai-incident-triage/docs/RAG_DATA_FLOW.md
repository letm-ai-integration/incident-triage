# RAG Data Flow — Where Agents Get Their Data and How

This document explains the **complete data flow** of the incident-triage POC:

```text
model-data files → ingestion → FAISS vector store → retrieval →
Log / Kubernetes agents → investigation orchestrator → shared state →
incident identification → runbook lookup (by incident name) → RCA & final result
```

It is written so a developer can understand the pipeline end-to-end without
reading every source file. Every claim below points at the code that implements it.

---

## 1. Data Source

The single source of mock truth for the RAG system is:

```text
ai-incident-triage/model-data/
├── db_logs.txt                    # database service log lines        → logs collection
├── external_api_logs.txt          # third-party dependency log lines  → logs collection
├── logs_traces.txt                # application/trace log lines       → logs collection
├── incident_telemetry_logs.txt    # telemetry for newer scenarios     → logs collection
├── metrics.json                   # per-service metric timelines      → metrics collection
├── k8s_logs.json                  # pod-level k8s events/logs         → k8s collection
├── incident_k8s.json              # k8s events for newer scenarios    → k8s collection
└── deployment_events.json         # CI deployment events              → events collection
```

Incident *definitions* (the alert payload each triage run starts from) live next
to them, keyed by incident name and cross-referencing the same services as above:

```text
ai-incident-triage/data/incidents/*.json     # one JSON per mock incident
```

Runbooks are plain markdown with a strict convention (see §7):

```text
ai-incident-triage/runbooks/*.md             # named by incident name, e.g.
                                             # database-connection-failure.md
```

There are also curated operational knowledge files under
`knowledge_base/runbooks/runbook.md` and `knowledge_base/kubernetes/*.md`
which feed the same collections (§2) alongside `model-data`.

**Important invariant:** no agent hard-codes incident content. Agents only ever
receive documents returned from the vector store; anything added to
`model-data/` becomes retrievable after re-ingestion, with zero code changes.

---

## 2. Ingestion

### 2.1 Canonical rebuild script

`scripts/ingest_model_data.py` is the canonical entry point:

```bash
python scripts/ingest_model_data.py                  # everything
python scripts/ingest_model_data.py --collections logs k8s   # subset
```

It reads the physical files under `model-data/`, turns them into retrieval
chunks, and pushes them into five FAISS-backed collections via
`app/knowledge/vector_store.py::add_documents` (local embeddings from
`app/knowledge/embeddings.py`; storage in `vectorstore/<collection>/`):

| Collection | Files | Chunking strategy |
|------------|-------|-------------------|
| `logs`     | `db_logs.txt`, `external_api_logs.txt`, `logs_traces.txt`, `incident_telemetry_logs.txt` | raw lines grouped into ≤40-line **service-aligned** chunks (`app/knowledge/model_data.py::_chunk_by_service`) |
| `k8s`      | `k8s_logs.json`, `incident_k8s.json` | rows grouped per `(namespace, service)` pair **plus** one fine-grained chunk (`kind=k8s-event`) for every WARN/ERROR row so decisive events (ImagePullBackOff, OOMKilled, probe failures) stay sharply retrievable |
| `metrics`  | `metrics.json` (+ any other metrics file) | one timeline chunk per service |
| `events`   | `deployment_events.json` | one chunk per service |
| `runbooks` | `runbooks/*.md` + `knowledge_base/runbooks/runbook.md` | markdown sections via `app/knowledge/chunker.py::chunk_markdown_by_sections` |

The loader for all model-data files is **`app/knowledge/model_data.py`** — the
only bridge between the raw mock files and the vector store. Its public API is
`collection_source(collection_name)` which returns `SourceChunk(doc, metadata,
doc_id)` tuples, tagged with `source`, `source_file`, `service` (and
`namespace`/`kind` where applicable).

Service attribution matters: `_service_from_pod("backend-api-02") ->
"backend-api"` and `_service_from_txt()` extract `[service]` tokens or JSON
envelopes so the Log/Kubernetes agents can retrieve evidence that belongs to
*the incident's own service*.

Ingestion is idempotent — `add_documents` upserts deterministic ids such as
`model-data:k8s:<namespace>:<service>:<file>`, so re-running the script after a
mock-data change safely adds/updates only what changed.

Legacy/manual alternative for markdown knowledge files:
`scripts/ingest_knowledge.py --file <path> --collection <name>`
(the curated `knowledge_base/kubernetes/*.md` docs in the `k8s` collection were
ingested this way; they coexist with the model-data pod-log chunks).


---

## 3. Retrieval

The only module agents import for retrieval is **`app/knowledge/retriever.py`**:

```python
retrieve(collection: str, query_text: str, k: int = 3) -> list[RetrievedChunk]
# RetrievedChunk = (text, metadata, score)   # score = cosine similarity
```

It raises `VectorStoreCollectionMissing` when a collection has not been
ingested — callers must treat "not ingested" distinctly from "no results".

Per-agent collection mapping:

| Agent | Collection | Query built from | Implementation |
|-------|------------|------------------|----------------|
| LogAnalysisAgent | `logs` | incident service + title/description + alert keywords (`_collect_query`) | `app/agents/investigation/log_analysis/agent.py` |
| KubernetesAgent | `k8s` | incident service + description + pod/event vocabulary (`_build_query`) | `app/agents/investigation/kubernetes/agent.py` |
| RunbookAgent | `runbooks` | classification type/priority/services + title + description + logs (`_build_query`) | `app/agents/investigation/runbook/agent.py` |

Example trace — `INC-011 High API Latency` on `checkout-service`:

```text
LogAnalysisAgent  → retrieve("logs",      "checkout-service high api latency ...") → db/external/app log chunks tagged service=checkout-service
KubernetesAgent   → retrieve("k8s",       "checkout-service pods restart ...")     → k8s_logs.json / incident_k8s.json rows for that namespace+service
RunbookAgent      → retrieve("runbooks",  "incident type: ... title: High API Latency") → runbook sections; resolver matches by name (§7)
```

---

## 4. Agent Processing

Each investigation sub-agent follows the same contract:

```text
receive Incident (+ ClassificationResult) → build RAG query → retrieve(k)
→ include retrieved chunk texts verbatim in the LLM prompt as "Retrieved context"
→ LLM analyses ONLY that context (deterministic keyword fallback when no LLM)
→ structured findings: Evidence(+Hypothesis) with findings grounded in the chunks
```

* **LogAnalysisAgent** (`log_analysis/agent.py`): queries the `logs` collection,
  logs `[PROCESS] querying log RAG … retrieved N documents`, feeds the chunk
  texts to the LLM prompt (retrieved log evidence is labelled by source file +
  service), and returns an `Evidence` whose finding summarises *what the mock
  logs show* (e.g. DB connection failures), never LLM-invented telemetry.
* **KubernetesAgent** (`kubernetes/agent.py`): same pattern over the `k8s`
  collection; findings cite pods/restart counts/reasons coming from the model-data rows.
* Both have deterministic fallbacks when no chat LLM is configured — the
  fallback still consumes the retrieved chunks.

Lifecycle logging: every agent emits `[AGENT]/[SUBAGENT] [ENTRY|PROCESS|OUTPUT|EXIT|ERROR]`
lines via `app/logging_utils.py` so a run's trace shows exactly what each agent
achieved (documents retrieved, findings identified) without dumping payloads.

---

## 5. Investigation Orchestration and Shared State

The orchestrator (`app/agents/investigation/orchestrator.py`) is the single
owner of the investigation phase. It executes a compiled LangGraph subgraph
(`subgraph.py`) that fans out three parallel nodes and aggregates:

```text
START ──┬─> log_analysis ───┐
        ├─> kubernetes ─────┼──> synthesize_outcome ──> END
        └─> runbook ────────┘
```

`_synthesize_outcome` merges per-subagent `Evidence` items into
`evidence` / `hypotheses` / `confidence`. The orchestrator maps this onto
`InvestigationOutcome`, and `app/services/investigation_service.py::investigation_service`
writes it into the shared graph state (`IncidentState`, `app/graph/state.py`):

```python
state["evidence"]              # all Evidence items
state["hypotheses"]            # ranked Hypotheses
state["log_analysis"]          # per-subagent Evidence
state["kubernetes_analysis"]
state["runbook_analysis"]
state["runbook_name"]          # display name of a matched runbook (or None)
state["runbook_solution"]      # verbatim Solution section of that runbook (or None)
```

This is how downstream agents consume investigation output — nothing stays
isolated inside the orchestrator.

---

## 6. Downstream Agents → Final Result

After `investigation`, the top-level graph continues
(`app/graph/workflow.py`):

```text
ingestion → classification ─┬─> full_investigation ─> investigation ─> investigation_summary
                            └─> auto_resolve ────────────────────────────────┐
                                                                             │
        rca_report → approval → verification ─> completed/reinvestigate <────┘
```

* **investigation_summary** aggregates evidence into `state["investigation_summary"]`.
* **rca_report** (`app/services/rca_report_service.py`) builds
  `RootCauseAnalysis` from the shared evidence/hypotheses. **Runbook-backed
  resolution lands here:** when `state["runbook_name"]` and
  `state["runbook_solution"]` are set it emits

```python
expected_outcome = {
    "expectation": f"Incident resolved by addressing '{runbook_name}'.",
    "action": ('A matching runbook was found for "<name>". '
               'The recommended resolution from the runbook is: <solution>'),
}
```

and attaches a `RunbookReference` to the rendered report ("Related Runbooks").
When there is no matching runbook, the normal root-cause-driven expectation is
used instead — nothing is fabricated.
* **verification** compares against `expected_outcome`; unresolved runs loop
  back into `investigation` (`route_after_verification`).
* **notification** renders/pushes the final result.

---

## 7. Runbooks — Lookup by Incident Name

Files follow this convention (`app/agents/investigation/runbook/resolver.py`):

```markdown
# <Incident Display Name>

## Overview
...

## Solution          ← required for a match to be usable
<resolution text>

## Troubleshooting
...
```

The RunbookAgent uses two complementary signals:

1. **Name-based lookup** (authoritative): `resolver.resolve_by_name(title,
   description)` token-matches the incident title/description against each
   runbook's `# Display Name`, and only returns a doc that has a `## Solution`.
   Its solution text is copied verbatim into
   `RunbookResult.resolution = 'A matching runbook was found for "<name>". The
   recommended resolution from the runbook is: <solution>'`, which reaches the
   final result through §6.
2. **Semantic FAISS retrieval** over the `runbooks` collection supplies a
   relevance score used in evidence weighting (threshold:
   `MIN_RELEVANCE_SCORE = 0.45`).

Behaviour matrix:

| Case | Behaviour |
|------|-----------|
| Match with `## Solution` | Runbook name + verbatim solution surface in the final result |
| No name match | `NO_MATCH` → normal analysis path |
| Match but no/empty `## Solution` | Not treated as matched → normal analysis path |
| Retrieval error | Falls back to name-lookup if usable, else `ERROR` status |

The agent never invents a resolution: no named-runbook hit ⇒ no runbook claim
anywhere in the output.

---

## 8. Ingestion Approval Nodes — What They Actually Are

Terminology disambiguation (important):

* There is **no approval gate in front of RAG/FAISS ingestion**. RAG ingestion
  is an offline, developer-triggered script (`scripts/ingest_model_data.py`);
  it never enters a LangGraph run and cannot be blocked by any node.
* The graph's `ingestion` node (`app/graph/nodes/ingestion.py`) normalises the
  raw alert payload into the domain `Incident` model — *incident input*
  ingestion, not vector-store ingestion.
* The graph's `approval` node (`app/graph/nodes/approval.py`) is the
  human-in-the-loop checkpoint **after RCA, before verification/notification**:

```text
Incident input → Ingestion(normalise) → Classification → Investigation
      → Summary → RCA Report
                     ↓
              [Approval Node]   ← HITL sign-off gate
                ↙         ↘
         approved       rejected
             ↓               ↓
        verification    notification (rejection)
```

Why it exists / what it protects:

* **What state it operates on:** reads the built `IncidentReport`
  (`state["incident_report"]`), `classification.priority`, and confidence.
* **Policy:** `_default_approve` requires sign-off when priority ∈ {P1, P2} or
  classification confidence is below the default threshold, *unless*
  `deps["auto_approve"]` is enabled (default in POC). A production policy
  service would be injected via `deps["approval_service"]`.
* **On approval:** an `ApprovalDecision(approved=True)` is recorded on state +
  incident report; router (`router.route_after_approval`) continues to
  `verification`.
* **On rejection:** decision recorded, routed straight to `notification`
  (the workflow ends without automated remediation/verification).
* **Is it required?** It does not block or gate Log/K8s RAG in any way. For the
  POC it auto-approves; it exists so the HITL seam for a production rollout is
  already wired and tested rather than retro-fitted later. Keep it.

---

## 9. Re-ingesting After Mock-Data Changes

```bash
cd ai-incident-triage
python scripts/ingest_model_data.py            # rebuild/update all collections
```

Then verify retrieval actually sees the new data (do not stop at "script ran"):

```bash
python - <<'PY'
from app.knowledge.retriever import retrieve
for coll, q in [("logs", "your-service your symptom"), ("k8s", "your-service pod"),
                ("runbooks", "your incident name")]:
    chunks = retrieve(collection=coll, query_text=q, k=3)
    print(coll, [(c.metadata.get("source_file"), c.score) for c in chunks])
PY
```

Checklist for adding a new mock incident (keeps everything synchronized):

1. `data/incidents/<name>.json` — incident definition (title matches runbook name when applicable).
2. Log evidence under `model-data/` tagged with the same service.
3. Kubernetes events under `model-data/k8s_logs.json` or `model-data/incident_k8s.json`.
4. Optional `runbooks/<name>.md` with `## Solution`.
5. Re-run `scripts/ingest_model_data.py`.
6. Check per-scenario expectations under `docs/scenario_answer_keys/`.
