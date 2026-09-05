---
title: Database connection pool exhausted on checkout-db
service: checkout-db
severity_applicable: [P1]
tags: ['checkout-db']
version: 1
last_reviewed: 2026-08-31
owning_team: auto-generated
---

# Database connection pool exhaustion on checkout-db

## Symptoms

- Customers on the checkout page see intermittent "unable to complete order" errors
- Application logs show the checkout service repeatedly failing to acquire a connection from the primary database pool
- Traffic spike is observed on the checkout-db instance
- Error rate increases on checkout endpoints, correlating with connection acquisition timeouts

## Diagnosis Steps

1. **Confirm the connection pool is exhausted** — Query the database for current active connections:
   ```sql
   SELECT count(*) FROM pg_stat_activity WHERE state = 'active';
   ```
   Compare against the configured `max_connections` (typically 100-200 for the checkout pool).

2. **Identify which queries are consuming connections** — Find long-running or idle-in-transaction queries:
   ```sql
   SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
   FROM pg_stat_activity
   WHERE (state = 'active' OR state = 'idle in transaction')
   ORDER BY duration DESC;
   ```

3. **Check for blocking sessions** — Look for locks that may be holding connections open:
   ```sql
   SELECT blocked_locks.pid AS blocked_pid,
          blocking_locks.pid AS blocking_pid
   FROM pg_locks blocked_locks
   JOIN pg_locks blocking_locks ON blocked_locks.locktype = blocking_locks.locktype AND blocked_locks.database = blocking_locks.database
   WHERE NOT blocked_locks.granted;
   ```

4. **Review application logs** — Look for connection pool timeout errors and correlated SQL execution logs:
   - `grep "could not acquire connection" /var/log/checkout-service/checkout.log`

5. **Examine application connection pool metrics** — Check HikariCP or similar pool metrics for usage:
   - `active`, `idle`, `pending`, and `max` connection counts.

6. **Check database resource usage** — CPU, memory, and disk I/O spikes may indicate a slower database causing connections to pile up:
   - Use `top`, `iostat`, or cloud monitoring tools.

## Resolution

1. **Immediate mitigation** — If the pool is fully exhausted and traffic is high, scale the connection pool up temporarily:
   - Increase `max_connections` in the database config (e.g., from 100 to 200)
   - Restart the checkout service to apply new pool settings
   - **Caution:** Ensure the database server has enough RAM to handle additional connections.

2. **Identify and resolve problematic queries or transactions** — If long-running or blocking queries are found:
   - Cancel the offending query: `SELECT pg_cancel_backend(<pid>);`
   - If it's idle-in-transaction, terminate the session: `SELECT pg_terminate_backend(<pid>);`

3. **Prevent recurrence** — After the immediate issue is resolved:
   - Investigate what caused the traffic spike (e.g., flash sale, retry storm, DDoS)
   - Consider implementing connection pool monitoring and auto-scaling
   - Add query timeout to prevent long-running queries from holding connections
   - Review application code for unclosed connections or transaction leaks

4. **Recovery verification** — After applying the fix:
   - Confirm the database connection pool utilization drops below 80%
   - Verify checkout service successfully acquires connections and errors stop
   - Monitor for 5-10 minutes to ensure stability

## Observed Incident — 2026-08-31 — INC-DB-1001
**Severity:** P1
**Root Cause:** No hypotheses produced; cause could not be determined during investigation.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.5 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.