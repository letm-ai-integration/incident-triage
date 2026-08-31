# Database Connection Failure

## Overview
The application cannot reach or acquire a connection from the primary database,
usually surfacing as `Connection refused`, `connection pool exhausted`, or
`SQLTransientConnectionException`. Root causes are typically one of: DB server
down/restarting, network partition to the DB, a saturated connection pool (with
or without a connection leak), or max-connection exhaustion at the server.

## Solution
1. Verify DB server health and connectivity from the affected pod:
   `kubectl exec <pod> -- nc -vz <db-host> <port>` and check the DB server logs.
2. Inspect pool metrics (active/idle/waiting/utilization). If utilization is
   pinned at 100% while request traffic is flat, suspect a **connection leak**:
   rolling-restart the application to reclaim leaked connections, then fix the
   unclosed-connection code path (file a follow-up bug).
3. If due to a traffic burst, raise the pool `maximumPoolSize` if the database
   can sustain it.
4. Check DB server `max_connections` and per-service allowances; raise them and
   review quotas if threads are blocked.
5. Confirm recovery: pool waiters drain, success rate returns to baseline, and
   no new timeouts for at least 15 minutes.

## Troubleshooting
- `pool utilization=100%` + `waiting` climbing + `slow_query_log: 0` → leak, not
  slow queries.
- `connection acquisition wait time p95 approaching timeout` → the pool is
  saturated right now; restart/scale first, then investigate the leak.
- DB-side FATAL "remaining connection slots are reserved" → server-level
  `max_connections` hit; raise limits or reduce client pool sizes.
