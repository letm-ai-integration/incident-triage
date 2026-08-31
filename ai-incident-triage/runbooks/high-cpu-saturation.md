# High CPU Saturation

## Overview
A workload's CPU usage pins near its limit, degrading throughput and increasing
latency. Causes: an inefficient hot path, a tight loop / busy-wait leak, an
abnormally high request burst, or too few replicas for the load. Characterised
by `cpu_pct` flatlining near 100% while `requests_per_sec` stays flat or rises.

## Solution
1. Confirm `cpu_pct` is pinned and identify the workload/pods pegging CPU.
2. Check `requests_per_sec` vs `cpu_pct`: flat load + high CPU points to a code
   regression (hot path / busy loop) — roll back if deployment-correlated.
3. If load genuinely spiked, scale the deployment (more replicas) and/or raise
   CPU request/limits if the node can sustain it.
4. Capture a CPU profile (e.g. jstack/async-profiler) on a burning pod to find
   the hot method; fix and re-release.
5. Confirm recovery: CPU utilisation returns under a healthy threshold and
   latency/SLO recovers.

## Troubleshooting
- `cpu_pct` ~100% with flat traffic → code/regression, not capacity.
- `cpu_pct` ~100% with rising traffic → capacity; scale out.
- High CPU + high latency together → saturating CPU starving the request path.
