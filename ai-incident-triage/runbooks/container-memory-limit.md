# Container Memory Limit / Steady-State Under-Provisioning

## Overview
A container's memory usage sits at ~100% of its configured limit with no
growing trend — the workload is simply under-provisioned for steady-state
load. Flat saturation (no leak signature) is the discriminating signal: the fix
is capacity, not a code change.

## Solution
1. Increase the memory limit with 20–30% headroom above steady-state:
   ```yaml
   resources:
     requests:
       memory: "1Gi"
     limits:
       memory: "1.5Gi"   # or "2Gi" depending on spike behavior
   ```
2. Re-apply and watch steady-state usage stay below ~70–80% of the new limit.
3. If usage starts climbing over time instead of staying flat, re-open the
   case — growth-over-time is a leak signature, not under-provisioning.

## Troubleshooting
- Flat `memory_pct ≈ 100%` + no upward trend across many hours → steady-state
  under-provisioning; raise the limit.
- `memory_pct` climbing monotonically until OOMKill → leak; investigate the
  allocation path before just raising the limit.