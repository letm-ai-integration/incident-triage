---
title: Database connection pool exhaustion on checkout-db
service: checkout-db
severity_applicable: [P1]
tags: ['checkout-db']
version: 1
last_reviewed: 2026-09-02
owning_team: auto-generated
---

# Database Connection Pool Exhaustion on checkout-db

## Symptoms
- Customers on the checkout page see intermittent "unable to complete order" errors.
- Application logs from the checkout service show repeated "failed to acquire connection from pool" errors against the primary database (`checkout-db`).
- The issue correlates with a traffic spike.

## Diagnosis Steps
1. Confirm the alert: Log into the monitoring dashboard and verify the `checkout-db` connection pool utilization metric is at or near 100%.
2. Check the database server's current number of active connections (e.g., `SELECT count(*) FROM pg_stat_activity` on PostgreSQL) and compare it against the configured `max_connections` / pool size.
3. Review application error logs for the checkout service to identify the frequency and timing of "connection acquisition" failures.
4. Inspect recent query performance: Look for long-running or blocked queries that could be holding connections open (e.g., `pg_stat_activity` with state `active` for > 30 seconds).
5. Correlate with traffic patterns: Is the traffic spike expected (e.g., flash sale, marketing campaign) or anomalous (e.g., bot attack)?
6. Verify if any code deployment or configuration change occurred to the checkout service or database connection pool settings shortly before the incident.

## Resolution
1. **Immediate mitigation:** Temporarily increase the database connection pool size on the checkout service (e.g., via environment variable or config push) to handle the spike. *Note: This should be done in coordination with database capacity planning to avoid overloading the database server.*
2. **If long-running queries are found:** Kill the offending queries immediately: `SELECT pg_terminate_backend(pid)`.
3. **If the root cause remains unknown (as in the referenced incident):** Apply the standard runbook fix for "No hypotheses produced":
   - Restart the checkout service pods to reap any stuck connections.
   - Validate that the number of active connections returns to a normal baseline.
   - Monitor the connection pool utilization over the next 15 minutes.
4. **Post-recovery:** Investigate further to determine the underlying cause (e.g., transaction leaks, slow queries, application bug) and implement a permanent fix (e.g., connection pool tuning, query optimization, adding read replicas).

## Observed Incident — 2026-09-02 — INC-DB-1001
**Severity:** P1
**Root Cause:** No hypotheses produced; cause could not be determined during investigation.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.5 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.

## Observed Incident — 2026-09-02 — INC-TEST-AMBIG

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- Customers on the checkout page see intermittent "unable to complete order" errors.
- Application logs from the checkout service show repeated "failed to acquire connection from pool" er
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-TEST-AMBIG

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- Customers on the checkout page see intermittent "unable to complete order" errors.
- Application logs from the checkout service show repeated "failed to acquire connection from pool" er
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-03 — INC-006

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- Customers on the checkout page see intermittent "unable to complete order" errors.
- Application logs from the checkout service show repeated "failed to acquire connection from pool" er
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.
