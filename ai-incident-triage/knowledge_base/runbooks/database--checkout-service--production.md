---
title: Database Connection Pool Exhaustion on checkout-service
service: checkout-service
severity_applicable: [P1]
tags: ['checkout-service', 'checkout-db']
version: 1
last_reviewed: 2026-08-31
owning_team: auto-generated
---

# Database Connection Pool Exhaustion on checkout-service

## Symptoms
- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database connection pool (HikariCP) metrics in monitoring dashboard report **100% utilization** (active + pending connections = maxPoolSize)
- Connection acquisition attempts time out under sustained checkout load
- Alert fires: "Database connection pool at 100% utilization, connection acquisition timeouts"

## Diagnosis Steps
1. **Verify the alert:** Check monitoring dashboards for `checkout-db` connection pool metrics – confirm pool is at 100% and active connections are stuck.
2. **Inspect active connections:** Run `SELECT * FROM pg_stat_activity` (or equivalent for your DB) to see long-running queries or idle-in-transaction connections.
3. **Check application logs:** Look for stack traces or logs indicating slow queries, blocked transactions, or high concurrency.
4. **Identify the bottleneck:** If queries are slow, examine `pg_stat_statements` or slow query logs. If queries are fast but pool is full, the issue is likely too many concurrent requests or a leak (connections not returned).
5. **Correlate with load:** Review traffic spikes (e.g., from a promotion) that may have overwhelmed the pool despite sufficient database capacity.

## Resolution
Apply the following fix based on the root cause:

1. **Increase connection pool size** (temporary workaround):  
   - Update `spring.datasource.hikari.maximum-pool-size` in the application configuration.  
   - This allows more concurrent connections but may shift the bottleneck to the database.  
   - **Caution:** Ensure the database has enough `max_connections` to accommodate.

2. **If the cause is slow queries or blocked transactions:**  
   - Kill long-running or stuck queries: `SELECT pg_terminate_backend(pid)` for problematic PIDs.  
   - Optimize or index the identified queries.  
   - Scale the database (e.g., read replicas, increase CPU/memory).

3. **If the cause is a connection leak:**  
   - Check for unclosed `DataSource.getConnection()` calls or missing `finally` blocks.  
   - Reduce `spring.datasource.hikari.idle-timeout` and `spring.datasource.hikari.max-lifetime` to recycle connections faster.

4. **Long-term mitigation:**  
   - Implement connection pooling monitoring and auto-scaling triggers.  
   - Add rate limiting or queueing at the ingress layer to smooth load spikes.

Monitor pool utilization and confirm recovery: pending connections drop to zero and active connections stay below the new limit.

## Observed Incident — 2026-08-31 — INC-006
**Severity:** P1  
**Root Cause:** Database Connection Pool Exhausted – primary cause relates to pool saturation at 100% under sustained checkout load, leading to connection acquisition timeouts.  
**Alert:** Database connection pool at 100% utilization, connection acquisition timeouts  
**Severity:** Critical  
**Routing:** prodCritical / databaseOnCall  
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.

## Observed Incident — 2026-08-31 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-08-31 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-08-31 — INC-006

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-08-31 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-08-31 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-006

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-006

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-006

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-006

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-006

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-006

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-006

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-006

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-006

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-006

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-006

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-DB-1001

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- `checkout-service` logs show `hikari-pool-1 - Connection is not available, request timed out after Xms`
- Customers receive "unable to complete order" errors during checkout
- Database 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.
