# High API Latency

## Overview
API response latency (p95/p99) spikes well above baseline, often accompanied by
HTTP 503/unavailable responses and elevated error rates. Typical triggers:
upstream dependency (DB, cache, third-party API) slowdown, JVM heap/gc
pressure, CPU saturation, or a traffic spike overwhelming capacity.

## Solution
1. Identify the slow endpoints and confirm the latency step-change in metrics
   (`p95`, `p99`, `gc_pause_ms`, `cpu_pct`).
2. Check upstream dependency health first — DB connection pool, cache, and any
   external provider. A slow upstream manifests as latency on the caller.
3. Check JVM/resources: high heap usage + long GC pauses point to memory
   pressure; high CPU → scale out or optimise.
4. Correlate with a recent deployment or traffic spike; roll back a bad release
   or scale the deployment for a burst.
5. Confirm recovery: latency returns to baseline p95/p99 for a sustained
   window, 5xx/unavailable rate drops, and SLO burn stops.

## Troubleshooting
- `503` + `readiness probe failed` + high heap → probe/health gating; fix probe
  or the dependency it checks.
- High `gc_pause_ms` + high heap → memory leak or undersized heap; raise limit /
  fix leak.
- Latency + high upstream p95 → external dependency; check the provider and
  circuit breaker instead of local scaling.
