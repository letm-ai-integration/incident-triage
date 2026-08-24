# INC-002: OOMKilled — Answer Key

**Actual root cause:** Application-level memory leak in the session-cache
layer (`SessionCache`) — entries stored with `ttl=none`, eviction policy NONE,
heap filled over ~20 minutes until the container hit its 1024Mi limit.

**Correct investigation trail:**
1. Metrics: `memory_pct` climbs steadily 61% -> 99.8% between 10:05 and
   10:24 (pod=cart-service-*); `gc_pause_ms` spikes late in the climb.
2. App logs (logs_traces, trace family `b0bcafe1*`): GC-pause warnings and
   `cache put ... ttl=none size=...` debug lines begin ~5 min before the
   first kill; the `OutOfMemoryError: Java heap space` stack trace inside
   `SessionCache.put` points at the leak site without saying "leak".
3. k8s_logs: OOMKilled / exit 137 events fire only at 10:24 and 10:26 —
   symptom, not cause.
4. deployment_events: last cart-service release (v1.9.3) completed ~2h before
   onset — rules out a bad recent release.

**Contributing factors:** none beyond the leak itself.
**Primary vs. secondary:** the OOMKilled event is the *symptom*; the memory
trend is the *evidence*; there is no deployment correlation to mislead toward
a release-based cause.
**Red herrings present:** orders-07 benign rolling restart at 10:08;
payments-16 staging disk warning at 10:12; auth TokenService clock-skew warn.
**Expected resolution:** restart + raised memory limit as mitigation; cache
TTL/eviction fix as follow-up (mirrors runbook "Pod CrashLoopBackOff
(OOMKilled)").
