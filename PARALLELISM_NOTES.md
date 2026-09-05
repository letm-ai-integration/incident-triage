# Parallelism finding — investigation sub-agents

**Finding (as of 2026-09-02):** the sub-agent calls inside the `investigation`
node currently run **in parallel**, via **LangGraph's own async fan-out**
(the compiled investigation-phase subgraph schedules the three child nodes
concurrently), not via an explicit `asyncio.gather`/thread-pool call in our
code.

## Mechanism

`run_investigation` (`app/agents/investigation/orchestrator.py`) invokes the
compiled subgraph:

```python
result = await investigation_phase_graph.ainvoke(...)
```

That subgraph (`app/agents/investigation/subgraph.py`) is defined with a
parallel branch:

```
START ──┬─> log_analysis ───┐
        ├─> kubernetes ─────┼──> synthesize_outcome ──> END
        └─> runbook ────────┘
```

```python
for subagent in ("log_analysis", "kubernetes", "runbook"):
    builder.add_edge(START, subagent)
    builder.add_edge(subagent, "synthesize_outcome")
```

LangGraph sees three nodes with no inter-dependencies after `START` and
executes them concurrently in its async task scheduler: each node is
dispatched as an independent task and the runtime `await`s them together, so
the three sub-agents genuinely overlap rather than running one-after-another.
`synthesize_outcome` is a barrier that aggregates only after all three
complete. In **LLM-less mode** each sub-agent is a fast keyword fallback, so
the overlap is milliseconds; with an LLM configured the parallelism is what
actually hides per-agent model latency.

## Empirical evidence (real run, no LLM)

Trace timestamps captured from a live stream of
`data/incidents/database-connection-failure.json` via the event-bus
`agent_trace` (`type == "subagent"`):

| Sub-agent | started_at | ended_at | duration_ms |
|---|---|---|---|
| log_analysis | 01:28:15.283042 | 01:28:15.283080 | 0.038 |
| kubernetes   | 01:28:15.283178 | 01:28:15.785041 | 501.863 |
| runbook      | 01:28:15.283292 | 01:28:16.140905 | 857.613 |

All three started within ~0.3 ms of each other, `kubernetes` and `runbook`
time windows overlap almost entirely, and the whole `investigation` node took
864 ms — about the same as the longest single sub-agent (runbook, 858 ms) —
which is the signature of concurrent execution, not a sequential pipeline.

## UI visibility

The live graph canvas already renders this fan-out: `investigation` is drawn
as a cluster with one child pill per sub-agent, each with its own live
status/duration, and the detail panel lists the per-sub-agent input/output.

## Status

Documented for a future decision — **no behaviour change was made** as part of
this task.