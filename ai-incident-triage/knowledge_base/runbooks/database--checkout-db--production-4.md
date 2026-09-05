---
title: Checkout Database Connection Pool Exhaustion
service: checkout-db
severity_applicable: [P1]
tags: ['checkout-db']
version: 1
last_reviewed: 2026-09-02
owning_team: auto-generated
---

# Checkout Database Connection Pool Exhaustion

## Symptoms
- Customers receive intermittent "unable to complete order" errors on the checkout page.
- Checkout service logs show repeated failures to acquire a connection from the primary database pool.
- Spike in traffic (e.g., flash sale or campaign) correlates with the onset of errors.
- `db_pool_active_connections` shows utilization at 100% with a growing wait queue.
- `db_pool_wait_queue_depth` increases while connection acquisition latency rises above 100ms p95.

## Diagnosis Steps
1. Check the database pool utilization metric: `db_pool_active_connections` against the pool hard limit.
2. Inspect wait-queue depth in the database pool metrics to determine if connections are queued.
3. Review application logs for "unable to acquire connection" errors correlating with the pool metrics.
4. Query the database session listing (e.g., `pg_stat_activity`) to identify long-running queries holding connections.
5. Confirm the traffic spike source (e.g., flash sale, campaign) via traffic monitoring dashboards.

## Resolution
1. **Confirm the pool is the bottleneck:** Verify `db_pool_active_connections` is at 100% utilization with a growing wait queue.
2. **Restore headroom immediately:** Terminate long-running queries found in `pg_stat_activity` or the DB session listing. If available, scale read replicas to offload connections.
3. **Remove the pressure driver:** If a traffic spike (flash sale/campaign) is active, throttle the checkout endpoint using rate limiting or queueing to reduce request concurrency below the pool ceiling. Allow the pool to drain.
4. **Stabilise the pool config:**
   - Raise the pool's maximum connections.
   - Add a second read-pool if applicable.
   - Enable connection validation and set connection lifetime limits to recycle stale connections.
   - Reduce the default query timeout to prevent slow queries from pinning connections.
5. **Verify recovery:**
   - Confirm `db_pool_wait_queue_depth` returns to zero.
   - Ensure connection acquisition latency is back under 100ms p95.
   - Verify checkout error rate drops to baseline before resuming full traffic.

## Observed Incident — 2026-09-02 — INC-DB-1001
**Severity:** P1
**Root Cause:** No hypotheses produced; cause could not be determined during investigation.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.5 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.