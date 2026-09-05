---
title: Database Connection Pool Exhausted on checkout-db
service: checkout-db
severity_applicable: [P1]
tags: ['checkout-db']
version: 1
last_reviewed: 2026-09-02
owning_team: auto-generated
---

# Database Connection Pool Exhausted on checkout-db

## Symptoms
- Customers on the checkout page see intermittent "unable to complete order" errors.
- Application logs show the checkout service repeatedly failing to acquire a connection from the primary database pool.
- A traffic spike is observed (e.g., flash sale or marketing campaign).

## Diagnosis Steps
1. Check the database pool utilization metric: `db_pool_active_connections` vs. the configured pool hard limit.
2. Inspect the wait queue depth: `db_pool_wait_queue_depth` – a growing queue indicates saturation.
3. Confirm pool exhaustion: utilization at 100% and increasing wait queue confirm the pool is the bottleneck.
4. Identify long-running queries holding connections via `pg_stat_activity` (or equivalent DB session listing).
5. Verify the pressure driver: is there a current traffic spike? Check checkout endpoint request rate and concurrency.

## Resolution
1. **Restore headroom immediately:**  
   - Terminate long-running queries identified in Diagnosis (via `pg_terminate_backend` or DB console).  
   - Scale read replicas if available to offload read traffic.
2. **Remove the pressure driver:**  
   - If a traffic spike is active, throttle the checkout endpoint (rate limit or queue) so request concurrency drops below the pool ceiling, allowing the pool to drain.
3. **Stabilise the pool configuration:**  
   - Once the pool is drained, increase the pool's maximum connections (or add a second read-pool).  
   - Enable connection validation and lifetime limits to recycle stale connections.  
   - Reduce the default query timeout to prevent slow queries from pinning connections.
4. **Verify recovery:**  
   - Confirm `db_pool_wait_queue_depth` returns to zero.  
   - Connection acquisition latency should be under 100ms p95.  
   - Checkout error rate must drop to baseline before resuming full traffic.

## Observed Incident — 2026-09-02 — INC-DB-1001
**Severity:** P1  
**Root Cause:** No hypotheses produced; cause could not be determined during investigation.  
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.5 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.