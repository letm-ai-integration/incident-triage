# Readiness Probe Misconfiguration Remediation

## Overview
Replicas never become Ready because the readiness probe's `timeoutSeconds` is
shorter than the endpoint's real response time, so the ingress returns 503
"no ready endpoints". The process itself never crashed (restart count 0) — this
is a configuration problem, not service instability, and a restart is not the
fix.

## Solution
1. Verify readiness timeout/initial-delay/failure-threshold against measured
   readiness latency.
2. Adjust probe configuration to tolerate the validated latency.
3. Roll out via the normal deployment process.
4. Confirm all replicas become Ready and re-check availability/503 metrics.

## Troubleshooting
- Readiness probe `timeout=1s` failing while the endpoint responds in ~1.8s +
  restart count `0` → misconfigured timeout; raise it via this runbook.
- Readiness failing with process restarts > 0 → actual service problem; treat
  as instability, not config.