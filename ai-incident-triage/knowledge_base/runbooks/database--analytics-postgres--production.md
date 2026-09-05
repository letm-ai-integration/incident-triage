---
title: Persistent Volume Disk Exhaustion on analytics-postgres
service: analytics-postgres
severity_applicable: [P1]
tags: ['analytics-postgres']
version: 1
last_reviewed: 2026-09-02
owning_team: auto-generated
---

# Persistent Volume Disk Exhaustion on analytics-postgres

## Symptoms
- Persistent volume utilization reaches 100%, triggering a critical alert (`PVC utilization > 90% (warning) or 100% with write failures`).
- PostgreSQL writes fail, and the database switches to read-only mode to prevent data corruption.
- `INSERT`, `UPDATE`, and `DELETE` operations return disk-full errors.
- Autovacuum jobs fail, leading to bloat and further degradation.
- WAL segments accumulate due to a retention backlog (e.g., incomplete/inactive replication slots or misconfigured WAL archiving).
- Monitoring dashboards show disk space exhaustion on the analytics-postgres data volume.
- Application errors or increased latency due to inability to write.

## Diagnosis Steps
1. **Verify alert details**
   - Confirm the alert fired for the analytics-postgres pod and PVC (e.g., `pvc-xxxxx`).
   - Note the current utilization percentage from Prometheus/Grafana or `kubectl top pvc <pvc-name>`.

2. **Identify top space consumers**
   - Exec into the PostgreSQL pod: `kubectl exec -it <pod> -- bash`
   - Run `df -h` to see filesystem usage.
   - Check the data directory (usually `/var/lib/postgresql/data` or similar).
   - List largest directories: `du -sh /var/lib/postgresql/data/* | sort -rh | head -10`
   - Specifically examine WAL directory: `du -sh /var/lib/postgresql/data/pg_wal/`

3. **Check WAL accumulation**
   - List WAL segment files and count: `ls -la /var/lib/postgresql/data/pg_wal/ | wc -l`
   - Verify replication slots: `SELECT slot_name, active, restart_lsn FROM pg_replication_slots;`
   - If any slot is inactive or stuck, that prevents WAL cleanup.

4. **Inspect PostgreSQL logs**
   - Look for recent errors: `kubectl logs <pod> --tail=200 | grep -i error`
   - Confirm read-only mode: `SELECT pg_is_in_recovery();` (should return `false` normally; if read-only due to disk, `true` after auto-demotion).

5. **Check PVC and storage backend**
   - `kubectl describe pvc <pvc-name>` for capacity and status.
   - If using cloud volumes (e.g., EBS, GCE PD), verify from provider console for any anomalies.

6. **Correlate with recent changes**
   - Review deployments, configuration changes, or WAL archiving modifications. Check if a new replication slot was added or retention policy changed.

## Resolution
1. **Immediate relief (recover write capability)**
   - If the database is in read-only mode due to disk full, free disk space to allow PostgreSQL to recover:
     1. Identify and remove unnecessary WAL segments if replication slots are healthy:
        - `SELECT pg_switch_wal();` – force a WAL switch after freeing some space.
        - Manually delete old WAL files only if absolutely necessary and replication is not compromised. **Preferred**: allow PostgreSQL to recycle via checkpoint.
     2. Clear any archive backlog: remove old archived WAL files from the WAL archive directory (if separate).
     3. If possible, temporarily increase PVC size:
        - Edit PVC definition: `kubectl edit pvc <pvc-name>` and increase `spec.resources.requests.storage`.
        - Wait for the resize to complete and confirm with `kubectl get pvc`.

2. **Remove large temporary or unnecessary data**
   - Drop unused indexes or materialized views.
   - Truncate or drop staging tables that are no longer needed – but **caution** with production data.
   - Run `VACUUM FULL` only if absolutely required and downtime can be tolerated (takes locks). Prefer `VACUUM` (simple) to free space for future writes.

3. **Post‑recovery steps**
   - Verify the database exited read‑only mode: `SELECT pg_is_in_recovery();` → `f`.
   - Test writes: `CREATE TABLE test_recovery (id int); INSERT INTO test_recovery VALUES (1); DROP TABLE test_recovery;`
   - Resume autovacuum by checking `pg_stat_activity` for any stuck backends.
   - Validate replication slots are active and WAL is being archived properly.

4. **Prevent recurrence**
   - Set up proactive monitoring with alarms at 80% and 90% utilization.
   - Configure automated PVC resize policies (e.g., Kubernetes cluster autoscaler for storage).
   - Review WAL retention: ensure replication slots are monitored and removed when no longer needed, and that WAL archiving completes successfully.
   - Implement automated WAL cleanup or archive retention policies.

## Observed Incident — 2026-09-02 — INC-DISK-4006
**Severity:** P1
**Root Cause:** Primary cause relates to: ## Persistent Volume Disk Exhaustion

**Alert:** PVC utilization > 90% (warning) or 100% with write failures
(critical)
**Severity:** Critical
**Routing:** dbaOnCall / platformOnCall

**Impact:**
- Database became read‑only, blocking all write operations.
- Autovacuum failures caused index bloat and further degradation.
- Application experienced errors and data ingestion stalled.

**Resolution Evidence:** Diagnosis verified: root‑cause confidence 0.95 meets the threshold and a runbook‑recommended fix exists. No fix has been applied by this system; remediation is pending on‑call action.