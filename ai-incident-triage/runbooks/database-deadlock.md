# Database Deadlock Remediation

## Overview
Postgres aborts transactions with deadlock detection errors: independent
transactions take locks in conflicting orders and get rolled back, surfacing a
rising transaction error rate. Deadlocks and rollbacks are directly observed in
logs; the exact code path creating the lock-order inversion is not proven here
and needs further verification.

## Solution
1. Capture deadlock details and identify the conflicting transaction/lock order.
2. Standardize lock acquisition order where applicable.
3. Keep transactions short; avoid unnecessary lock duration.
4. Validate deadlock frequency/error rate after the change.

## Troubleshooting
- `deadlock detected` rollback pairs for distinct transactions, error rate above
  baseline → apply this runbook.
- Rollbacks without `deadlock detected` → different cause (constraint failures,
  timeouts); do not treat as a deadlock.