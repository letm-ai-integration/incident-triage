# Cache Stampede Remediation

## Overview
A cache (Redis) restart or eviction empties the hot set: hit rate collapses,
read traffic floods the backing database, and latency spikes until the cache
repopulates. Restart→load-spike timing is directly observed; that the restart is
the cause (vs another driver of the DB load) is a well-supported but inferred
conclusion.

## Solution
1. Confirm timing correlation between the Redis restart and the DB load spike.
2. If recurring, implement cache warm-up on Redis startup for high-traffic keys.
3. Add request coalescing/single-flight locking so concurrent misses for the
   same key trigger one DB read.
4. Add jittered TTL stagger on cache writes.
5. Consider a Redis replica/failover topology.

## Troubleshooting
- Redis restart/eviction event + hit-rate drop + pool exhaustion/DB QPS spike →
   apply this runbook.
- Hit-rate drop with no cache event → investigate other cache-invalidating
  changes before warming the cache.