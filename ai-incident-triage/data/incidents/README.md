# data/incidents

Committed mock incidents consumed by the triage graph.

## Schema

Canonical telemetry keys (mirror the `Incident` model in
`app/domain/models/incident.py`):

- `incident_id`, `title`, `description`, `source`, `service`, `environment`
  (uppercase enum string: `PRODUCTION` / `STAGING` / ...), `priority_hint`
  (`P1`–`P4`), `tags`, `timestamp` (ISO-8601)
- `raw_logs` — list of **one JSON object per line** (canonical fields
  `timestamp`, `sequence`, `loggerClassName`, `loggerName`, `level`, `message`,
  `threadName`, `threadId`, `mdc`, `processName`, `processId`, `IMAGE_TAG`,
  `region`, `environment`; per the Phase 6 worked-example).
- `raw_events` — list of `dict` (k8s event shape `{type, reason, object,
  message, timestamp}` or `{type, service, timestamp, description}`)
- `raw_alerts` — list of `dict` (`alert_name`, `severity`, `fired_at`, `labels`)
- `raw_metrics` — flat `dict` of numeric/string metrics
- `metadata` — `scenario_id`, `service`, `namespace`, `data_sources`, and
  (where a runbook applies) `runbook` referencing the top-level `runbooks/*.md`
  display name.

The ingestion node (`app/graph/nodes/ingestion.py`) reads `raw_*` keys first,
falling back to the legacy `logs` / `events` / `alerts` / `metrics` keys used by
`crashloopbackoff.json`, `database_timeout.json`, `http503.json`,
`imagepullbackoff.json`, and `unmatched-no-telemetry.json`.

## Contents

- INC-001..INC-014 era + INC-INC-SIM-3001 / INC-PERF-3077 / INC-K8S-*, ... — see
  the audit + phases in `../../NOTES.md` for the full inventory.
- Phase 6 added the **B–L** dataset (`INC-MEM-5006` `INC-OOM-5007`
  `INC-RATELIMIT-5008` `INC-DNS-5009` `INC-DISK-5010` `INC-CACHE-5011`
  `INC-AVAIL-5001` `INC-KAFKA-5002` `INC-DB-5003` `INC-TLS-5004`
  `INC-AVAIL-5005`) and normalized INC-006's logs to the JSON-object shape.

Mock verification outcomes live in `../outcomes/resolved/` and
`../outcomes/unresolved/`, and generated incident reports in `../reports/`.