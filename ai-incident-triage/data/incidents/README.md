# data/incidents

Mock incident inputs consumed by the CLI (`app/main.py <file>`) and the UI
sample pickers (`_load_samples()` loads every non-empty `*.json` here; the
filename stem becomes the sample name).

## Incident files

| File | ID | Root cause |
|---|---|---|
| `database-connection-failure.json` | INC-006 | DB connection pool exhausted on checkout-db under flash-sale load |
| `database_timeout.json` | INC-DB-1001 | Same pool-exhaustion story (legacy variant, kept for CLI demo) |
| `crashloopbackoff.json` | INC-K8S-2091 | Config deploy breaks auth-service pods (CrashLoopBackOff) |
| `imagepullbackoff.json` | INC-K8S-2001 | Bad image tag stuck in ImagePullBackOff |
| `http503.json` | INC-PERF-3077 | JVM heap saturation behind intermittent 503s |
| `deployment_regression.json` | INC-005 | Bad rollout regresses inventory-service |
| `third_party_timeout.json` | INC-004 | Payment gateway timeouts + circuit breaker |
| `service-availability-degradation.json` | INC-AVAIL-4001 | (A) Traffic spike outruns replica count / HPA lag |
| `container-high-memory.json` | INC-MEM-4002 | (B) Container at memory limit (~0% headroom), GC thrash |
| `oomkilled-crashloop.json` | INC-K8S-4003 | (C) OOMKilled (exit 137) kill/restart loop |
| `downstream-rate-limit.json` | INC-API-4004 | (D) Downstream 429 rate limiting cascading into 5xx |
| `dns-resolution-failures.json` | INC-NET-4005 | (E) CoreDNS resolution failures → intermittent timeouts |
| `disk-exhaustion.json` | INC-DISK-4006 | (F) Persistent volume 100% full, writes failing |
| `cache-stampede.json` | INC-CACHE-4007 | (G) Cache stampede after Redis restart |
| `telemetry-gap.json` | INC-CACHE-4008 | Ambiguous: session-cache misses after maintenance, no corroborating signal (exercises the reinvestigation loop) |
| `memory-oom.json` | INC-010 | Memory pressure / OOM on cart-service (deliberately runbook-less fixture) |

## Schema

All files share the raw_* shape (see `database-connection-failure.json` for the
reference): `incident_id`, `title`, `description`, `source`, `service`,
`environment`, `priority_hint`, `tags`, `timestamp`, `raw_logs` (list of log
lines — plain `TIMESTAMP LEVEL [service] message` style, or JSON log lines where
the source system emits JSON), `raw_events`, `raw_alerts`, `raw_metrics`, and
`metadata` with at least `scenario_id` (stable identifier — ingestion falls back
to this when no explicit `incident_id` is given), `service`, `namespace`,
`data_sources`, and `runbook` (title of the matching `## ` section in
`knowledge_base/runbooks/runbook.md`, retrieved via RAG).

Incidents are investigation scenarios: none of them is or was "resolved" by
this system — every run produces a diagnosis plus a recommended runbook fix.

Mock verification outcomes live in `../outcomes/resolved/` and
`../outcomes/unresolved/`, and generated incident reports in `../reports/`.

