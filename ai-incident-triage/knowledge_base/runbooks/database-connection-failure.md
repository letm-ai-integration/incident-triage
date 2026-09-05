---
title: Database Connection Failure
service: checkout-service
severity: P1
---

# Database Connection Failure

## Overview

Checkout requests cannot acquire a database connection: the connection pool on
the primary database (checkout-db) saturates under sustained checkout load,
connection acquisition waits hit the 30s timeout, and customers see "unable to
complete order". This runbook covers a pool exhausted by a traffic spike — not
a schema regression or a database outage.

## Solution

- **Confirm the pool is the bottleneck:** check `db_pool_active_connections`
  against the pool hard limit and the wait-queue depth; a saturated pool shows
  `utilization=100%` with a growing wait queue.
- **Restore headroom immediately:** terminate the long-running queries that are
  holding connections (identify them via `pg_stat_activity` / the DB's session
  listing) and scale read replicas if available.
- **Remove the pressure driver:** if a traffic spike (flash sale / campaign) is
  active, throttle the checkout endpoint (rate limit or queue) so request
  concurrency drops below the pool ceiling, and let the pool drain.
- **Stabilise the pool config:** with the pool drained, raise the pool's
  maximum connections (or add a second read-pool), enable connection
  validation/lifetime limits so stale connections are recycled, and reduce the
  default query timeout so a slow query cannot pin a connection.
- **Verify recovery:** confirm `db_pool_wait_queue_depth` returns to zero,
  connection acquisition latency is back under 100ms p95, and checkout error
  rate drops to baseline before resuming full traffic.

## Troubleshooting

- **Pool at 100% but wait queue empty** — connections are leaked/held, not
  contended: check for connections left unclosed by the application pool and
  for idle-in-transaction sessions.
- **Pool drains then immediately re-saturates** — the workload (not the pool
  size) is the problem: look at query volume per request and caching before
  scaling the pool further.
- **Only one client is affected** — verify that client's connection settings
  (pool size, timeout) rather than the shared database.