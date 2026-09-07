# Disk Space Exhaustion Remediation

## Overview
A persistent volume fills up and the database can no longer write WAL files
(`No space left on device`), forcing read-only recovery mode. The high-usage
figure is directly observed; which table/log stream drives the growth is an
inference from the trailing trend unless a per-table breakdown isolates it.

## Solution
1. Confirm free space on the affected PVC.
2. Immediate: prune/archive oldest `audit_log` partitions and clear
   already-shipped WAL segments.
3. Expand the PVC if the storage class supports online expansion.
4. Root-cause fix: add retention/partitioning on the unbounded-growth table.
5. Add disk-usage alerts at 80%/90% thresholds.

## Troubleshooting
- `No space left on device` + `FreeDiskSpaceFailed` PVC event at ~99% → apply
  this runbook; prune then size.
- Disk usage rising but still under 80% → monitor; no immediate action.