# Incident Runbook Knowledge Base

Each entry below documents a known alert: what it looks like, its impact,
and the path taken to root cause and resolve it. This file is manually
maintained. Run `python scripts/ingest_knowledge.py --file
knowledge_base/runbooks/runbook.md --collection runbooks` after editing to
push changes into the searchable index.

---

## High API Failures

**Alert:** More than 10 HTTP 5xx errors per minute (aggregate)
**Severity:** Critical
**Routing:** prodCritical / preProdCritical

**Impact:**
- Users seeing error pages
- Failed transactions
- Payment/cart failures
- Elevated support ticket volume

**RCA Path:**
1. Check the API gateway dashboard for which endpoint(s) are failing.
2. Check recent deployments — correlate failure onset with any release in
   the last 30 minutes.
3. Check upstream dependency health (DB, cache, third-party APIs) for
   simultaneous degradation.
4. Check pod-level logs for the failing service for stack traces/error
   patterns.

**Solution:**
- If correlated with a deployment: roll back immediately.
- If correlated with an upstream dependency: fail over or apply circuit
  breaker if configured; escalate to the owning team.
- If neither: escalate to on-call backend engineer with gathered evidence
  above.

---

## Pod CrashLoopBackOff (OOMKilled)

**Alert:** Pod restart count > 5 within 10 minutes, termination reason
OOMKilled
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- Reduced service capacity
- Potential request failures during restart windows

**RCA Path:**
1. `kubectl describe pod <pod>` — confirm OOMKilled as termination reason.
2. Check memory usage trend over last 24h — gradual climb (leak) vs.
   sudden spike (traffic burst).
3. Cross-reference recent deployments.

**Solution:**
- Roll back to last known-good image if deployment-correlated.
- If gradual leak: raise memory limit as temporary mitigation, file a
  follow-up ticket for the leak itself.

---

## ImagePullBackOff

**Alert:** Pod stuck in ImagePullBackOff — image cannot be pulled
**Severity:** Medium
**Routing:** platformOnCall

**Impact:**
- New pods fail to start, capacity drops
- Deployments cannot roll out new versions

**RCA Path:**
1. `kubectl describe pod <pod>` — read the image pull failure reason.
2. Verify the image tag exists in the registry (`docker manifest inspect`
   or the registry UI).
3. Verify the cluster's registry credentials — expired or missing
   `imagePullSecrets` are the most common cause.
4. Check for a typo in the image tag (wrong tag, missing `:`).

**Solution:**
- Fix the image tag/reference in the deployment manifest and re-apply.
- If credentials issue: rotate/update `imagePullSecrets` and patch the
  deployment; they propagate to new pods automatically on restart.

---

## HTTP 503 Service Unavailable

**Alert:** HTTP 503 responses exceeding 5% of request volume for 5 minutes
**Severity:** High
**Routing:** prodCritical

**Impact:**
- Downstream callers receive service-unavailable errors
- Failed user requests and retries

**RCA Path:**
1. Confirm which service/path returns 503 — check gateway and ingress logs.
2. Check the target service's readiness/liveness probes — failing probes
   mean no healthy endpoints behind the load balancer.
3. Check pod status and restart counts for the affected service.
4. Check upstream dependencies (DB connection pool, cache) for exhaustion.

**Solution:**
- If probes are failing: fix the readiness check or the underlying
  dependency the probe depends on.
- If capacity is exhausted: scale the deployment; check for a leak/burst in
  upstream connections.
- If the dependency (DB/cache) is the source: resolve or fail over that
  dependency first.

---

## Database Connection Pool Exhausted

**Alert:** Database connection pool at 100% utilization, connection
acquisition timeouts
**Severity:** Critical
**Routing:** prodCritical / databaseOnCall

**Impact:**
- Application threads block waiting for connections
- Spikes in request latency and 5xx errors
- Cascading service degradation as more services contend for connections

**RCA Path:**
1. Check connection-pool metrics (active/idle/waiting) on the affected
   service.
2. Look for connection leaks — unclosed connections in long-running
   requests are a common cause.
3. Correlate with any recent deployment or traffic spike.
4. Check DB server limits and per-user max connections.

**Solution:**
- Restart/scale the affected application to release leaked connections.
- If traffic burst: raise the pool max size if the database can sustain it.
- If leaked connections persist: roll back the release that introduced the
   leak and file a follow-up bug.
- If DB server-level limit: tune max_connections and review per-service
  allowances.

---
## Third-Party API Timeout

**Alert:** External dependency error rate > 20% or egress p95 latency > 5s
sustained for 5 minutes
**Severity:** High
**Routing:** prodCritical

**Impact:**
- Customer-facing transactions that depend on the third party fail or stall
- Retry storms amplify latency onto adjacent services

**RCA Path:**
1. Check outbound-call logs for the failing provider — distinguish timeouts
   vs. HTTP 5xx from the provider.
2. Confirm the provider status page / feed reports degradation.
3. Review circuit-breaker state transitions (OPEN/HALF_OPEN/CLOSED) for the
   dependency.
4. Verify no correlated local deployment — absence keeps blame external.

**Solution:**
- Keep the circuit breaker OPEN and serve fallback/queued processing until
  the provider recovers; escalate to the vendor if prolonged.
- After recovery, drain any deferred-work queues and reconcile in-flight
  transactions.

---

## Deployment Regression

**Alert:** New error class appearing within 15 minutes of a deployment, or
error rate jumping > 5x baseline post-rollout
**Severity:** Critical
**Routing:** prodCritical

**Impact:**
- Immediate user-facing errors on affected endpoints
- Possible readiness-probe failures reducing serving capacity

**RCA Path:**
1. Compare deployment events with first occurrence of the new error type.
2. Confirm the error class was absent before the rollout window.
3. Check metrics for the post-deploy error-rate step change.
4. Roll forward only if the fix is trivial; otherwise roll back.

**Solution:**
- Roll back to the previous known-good version immediately.
- File a follow-up bug with the stack traces captured during the window;
  re-release only after reproducing and fixing the failure.

---

## Service Availability Degradation (Traffic Spike)

**Alert:** Synthetic availability < 100% for a public endpoint, or request
rate > 3x the 7-day baseline with rising latency
**Severity:** Critical
**Routing:** prodCritical

**Impact:**
- Users see slow or failed page loads (503/504s)
- Availability SLO burn; potential revenue loss during campaigns
- Readiness-probe failures further reduce serving capacity

**RCA Path:**
1. Confirm the traffic-shape change: compare current request rate against the
   7-day baseline and check for campaign/marketplace events.
2. Check HPA behavior: desired vs. current replicas, stabilization windows,
   and how far scaling lagged behind demand.
3. Check saturation signals: CPU utilization, connect-queue depth, connection
   pools, and p99 latency trend.
4. Correlate readiness/liveness probe failures with the load peak.
5. Verify no concurrent deployment or configuration change coincided.

**Solution (recommendations — the on-call engineer applies the fix):**
- Scale up replicas manually to absorb the spike while the HPA catches up
  (or lower the HPA stabilization window / raise maxReplicas).
- Restart pods that are wedged by probe failures once capacity is in place.
- Add/verify upstream timeouts and load-shedding limits so queues drain
  instead of saturating.
- After the event, re-tune HPA parameters so reaction time matches the
  traffic-ramp shape.

---

## Container High Memory Usage

**Alert:** Container memory usage within 5% of its limit, or headroom ≈ 0%
for more than 5 minutes
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- Heavy GC pressure: latency spikes and slow probes
- One allocation burst away from an OOMKill
- Thread-pool saturation and request backlogs while GC dominates

**RCA Path:**
1. Confirm usage vs. limit from container metrics (working set vs. limit).
2. Check the GC log pattern: frequency and pause times of full GCs, and
   whether heap stays high after collection (live set) or drops (burst).
3. Correlate with recent changes: cache size increases, new features, or
   traffic bursts that raised live-set size.
4. Take a heap profile/dump if the app is still responsive.

**Solution (recommendations — the on-call engineer applies the fix):**
- Increase the memory limit to give real headroom: rule of thumb is 20–30%
  above steady-state usage. For example, if the app genuinely needs ~1 GB at
  steady state:
  ```yaml
  resources:
    requests:
      memory: "1Gi"
    limits:
      memory: "1.5Gi"   # or "2Gi" depending on spike behavior
  ```
- Review the in-process cache sizing that drove the growth; reduce entries or
  move it behind an eviction budget that respects the new limit.
- Tune GC (heap fractions) only after the limit is corrected.

---

## Downstream API Rate Limiting (HTTP 429)

**Alert:** Sustained 429 responses from a downstream/third-party API, or 5xx
rate on the owning service > 5% correlated with 429s
**Severity:** High
**Routing:** prodCritical / integrationOnCall

**Impact:**
- Calling service surfaces cascading 5xx errors to its callers
- Background sync/queue processing falls behind (lag grows)
- Retry storms amplify load on both sides

**RCA Path:**
1. Confirm the 429 source: check response headers (quota, reset window) from
   the downstream API and whether a quota change occurred.
2. Measure retry amplification: attempts per failed request and the effective
   backoff policy in force.
3. Check circuit-breaker state transitions and whether half-open probes are
   re-opening immediately.
4. Correlate 5xx rate and queue/sync lag with the 429 onset time.

**Solution (recommendations — the on-call engineer applies the fix):**
- Throttle request rate to the vendor's granted quota (client-side rate
  limiter / token bucket) instead of retrying into a hard limit.
- Add exponential backoff with jitter and honor the vendor's reset window;
  cap attempts so retries cannot amplify load.
- Keep the circuit breaker OPEN for the reset window and queue/defer work
  rather than failing fast into 5xx.
- Engage the vendor to raise the quota or get a per-client allowance.

---

## DNS Resolution Failures

**Alert:** Rising DNS SERVFAIL/NXDOMAIN/timeout rate from a service's
resolver, or intermittent connection timeouts to in-cluster hostnames
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- A fraction of requests stall and time out while resolution retries run
- Elevated p99 latency and 504s despite healthy CPU/memory
- Reconnect storms can add load to CoreDNS

**RCA Path:**
1. Confirm the failure mode is resolution (NXDOMAIN/SERVFAIL/timeouts), not
   connection refusal — check resolver logs and app UnknownHostException /
   i/o timeout patterns.
2. Check CoreDNS pod health, restarts, and upstream probe failures in the
   affected window.
3. Verify the target Service/endpoints still exist (a deleted Service
   produces clean NXDOMAIN; a degraded resolver produces timeouts).
4. Rule out resource exhaustion on the calling service (this failure mode
   shows nominal CPU/memory).
5. Correlate latency spikes with DNS failure bursts.

**Solution (recommendations — the on-call engineer applies the fix):**
- Restore/roll CoreDNS to a healthy state (restart the degraded pods, verify
  upstream connectivity) before touching the calling service.
- Add client-side resolver caching / negative-TTL tuning and connection
  reuse so each request does not re-resolve.
- Add retry with backoff around DNS-dependent connects; make timeouts
  explicit so callers fail fast instead of hanging.
- If a Service was deleted or renamed, restore the Service/endpoints.

---

## Persistent Volume Disk Exhaustion

**Alert:** PVC utilization > 90% (warning) or 100% with write failures
(critical)
**Severity:** Critical
**Routing:** dbaOnCall / platformOnCall

**Impact:**
- Database/ingest writes fail (No space left on device); WAL/checkpoints
  fail and the instance may go read-only to protect consistency
- Autovacuum/maintenance fails; queues build up behind the writes

**RCA Path:**
1. Confirm which filesystem/PVC is full and what consumed it: data growth,
   WAL accumulation, or a failed retention/cleanup job.
2. Check whether cleanup/retention jobs have been failing and since when.
3. Correlate ingest rate increases with the growth curve.
4. Verify the volume's size class and whether expansion is possible online.

**Solution (recommendations — the on-call engineer applies the fix):**
- Free space immediately and safely: complete/repair the retention cleanup,
  archive and remove old WAL segments only after a verified backup/checkpoint.
- Expand the persistent volume (or migrate to a larger volume class) to
  restore headroom — target < 70% steady-state utilization.
- Fix the failing cleanup job and add an alert at 80% utilization so this is
  caught before write failures begin.

---

## Cache Stampede After Redis Restart

**Alert:** Cache hit rate collapses (< 20% of baseline) right after a Redis
restart/eviction, with origin DB CPU/connection saturation
**Severity:** High
**Routing:** prodCritical / dbaOnCall

**Impact:**
- Origin database receives the full read path load simultaneously
- Connection pools exhaust; read latency and error rates spike
- Replication lag grows while the origin is saturated

**RCA Path:**
1. Confirm the cache event: restart/eviction time and whether the cache came
   back empty (no AOF/RDB restore, eviction policy flush).
2. Verify the load spike start time is immediately after the cache event and
   that miss rate went to ~100% — correlation in the logs is the signature.
3. Check origin connection pools, CPU, and whether identical queries run
   concurrently without coalescing.
4. Rule out organic traffic growth (compare request rate to baseline).

**Solution (recommendations — the on-call engineer applies the fix):**
- Warm the cache before restoring full read traffic (controlled warming or
  gradual traffic ramp).
- Add request coalescing (single-flight) so concurrent identical misses
  trigger one origin query, and TTL jitter so keys do not expire together.
- Configure the cache for durability across restarts (AOF/RDB restore) where
  the data shape allows it.
- Consider short-lived stale-serve (serve slightly stale values while one
  refresh runs) as stampede protection.

---

## Pod CrashLoopBackOff (Configuration Error)

**Alert:** Pod restart count > 5 within 10 minutes with exitCode=1 (application
startup failure), shortly after a config/secret/ConfigMap change
**Severity:** Critical
**Routing:** platformOnCall

**Impact:**
- Zero or reduced serving capacity for the affected service
- Request failures cluster-wide while no pod becomes healthy

**RCA Path:**
1. `kubectl describe pod <pod>` — check container exitCode and the last
   restart timing against the most recent config/secret deployment.
2. Read the pod's startup logs: missing file paths, unresolved placeholders,
   or invalid configuration values identify the broken reference.
3. Diff the ConfigMap/Secret/Helm values against the last known-good revision
   (mounted paths, key names, required fields).
4. Confirm the application's expected mount path versus what the new config
   actually mounts.

**Solution (recommendations — the on-call engineer applies the fix):**
- Roll back the ConfigMap/Secret/Helm change to the last known-good revision
  (or restore the expected mount path/key names) so pods can start.
- Verify all pods reach Ready before re-attempting the config change with the
  corrected values.
- Add a pre-deploy validation step (config render + schema check) so a broken
  reference cannot reach the cluster again.


## Observed Incident — 2026-08-31 — INC-K8S-2091

**Severity:** P1
**Root Cause:** Primary cause relates to: ## ImagePullBackOff

**Alert:** Pod stuck in ImagePullBackOff — image cannot be pulled
**Severity:** Medium
**Routing:** platformOnCall

**Impact:**
- New pods fail to start, capacity drops
- Deployme
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-08-31 — INC-005

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (Configuration Error)

**Alert:** Pod restart count > 5 within 10 minutes with exitCode=1 (application
startup failure), shortly after a config/secret/ConfigMap change
**Severi
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-08-31 — INC-K8S-2001

**Severity:** P3
**Root Cause:** Primary cause relates to: ## ImagePullBackOff

**Alert:** Pod stuck in ImagePullBackOff — image cannot be pulled
**Severity:** Medium
**Routing:** platformOnCall

**Impact:**
- New pods fail to start, capacity drops
- Deployme
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-08-31 — INC-K8S-2001

**Severity:** P3
**Root Cause:** Primary cause relates to: ## ImagePullBackOff

**Alert:** Pod stuck in ImagePullBackOff — image cannot be pulled
**Severity:** Medium
**Routing:** platformOnCall

**Impact:**
- New pods fail to start, capacity drops
- Deployme
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-010

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (OOMKilled)

**Alert:** Pod restart count > 5 within 10 minutes, termination reason
OOMKilled
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- Reduced service capa
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-K8S-2091

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (Configuration Error)

**Alert:** Pod restart count > 5 within 10 minutes with exitCode=1 (application
startup failure), shortly after a config/secret/ConfigMap change
**Severi
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-005

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (Configuration Error)

**Alert:** Pod restart count > 5 within 10 minutes with exitCode=1 (application
startup failure), shortly after a config/secret/ConfigMap change
**Severi
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-K8S-2001

**Severity:** P3
**Root Cause:** Primary cause relates to: ## ImagePullBackOff

**Alert:** Pod stuck in ImagePullBackOff — image cannot be pulled
**Severity:** Medium
**Routing:** platformOnCall

**Impact:**
- New pods fail to start, capacity drops
- Deployme
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-K8S-2001

**Severity:** P3
**Root Cause:** Primary cause relates to: ## ImagePullBackOff

**Alert:** Pod stuck in ImagePullBackOff — image cannot be pulled
**Severity:** Medium
**Routing:** platformOnCall

**Impact:**
- New pods fail to start, capacity drops
- Deployme
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-K8S-2001

**Severity:** P3
**Root Cause:** Primary cause relates to: ## ImagePullBackOff

**Alert:** Pod stuck in ImagePullBackOff — image cannot be pulled
**Severity:** Medium
**Routing:** platformOnCall

**Impact:**
- New pods fail to start, capacity drops
- Deployme
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-K8S-2001

**Severity:** P3
**Root Cause:** Primary cause relates to: ## ImagePullBackOff

**Alert:** Pod stuck in ImagePullBackOff — image cannot be pulled
**Severity:** Medium
**Routing:** platformOnCall

**Impact:**
- New pods fail to start, capacity drops
- Deployme
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-010

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (OOMKilled)

**Alert:** Pod restart count > 5 within 10 minutes, termination reason
OOMKilled
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- Reduced service capa
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-K8S-4003

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (OOMKilled)

**Alert:** Pod restart count > 5 within 10 minutes, termination reason
OOMKilled
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- Reduced service capa
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-CACHE-4007

**Severity:** P2
**Root Cause:** ## Cache Stampede After Redis Restart

**Alert:** Cache hit rate collapses (< 20% of baseline) right after a Redis
restart/eviction, with origin DB CPU/connection saturation
**Severity:** High
**Routing:** prodCritical / dbaOnCall

**Impact:**
- Origin database receives the full read path load simultaneously
- Connection pools exhaust; read latency and error rates spike
- Replication lag grows while the origin is saturated

**RCA Path:**
1. Confirm the cache event: restart/eviction time and whether the cache came
   back empty (no AOF/RDB restore, eviction policy flush).
2. Verify the load spike start time is immediately after the cache event and
   that miss rate went to ~100% — correlation in the logs is the signature.
3. Check origin connection pools, CPU, and whether identical queries run
   concurrently without coalescing.
4. Rule out organic traffic growth (compare request rate to baseline).

**Solution (recommendations — the on-call engineer applies the fix):**
- Warm the cache before restoring full read traffic (controlled warming or
  gradual traffic ramp).
- Add request coalescing (single-flight) so concurrent identical misses
  trigger one origin query, and TTL jitter so keys do not expire together.
- Configure the cache for durability across restarts (AOF/RDB restore) where
  the data shape allows it.
- Consider short-lived stale-serve (serve slightly stale values while one
  refresh runs) as stampede protection.

---
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8064307570457458 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-MEM-4002

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (OOMKilled)

**Alert:** Pod restart count > 5 within 10 minutes, termination reason
OOMKilled
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- Reduced service capa
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-K8S-2091

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (Configuration Error)

**Alert:** Pod restart count > 5 within 10 minutes with exitCode=1 (application
startup failure), shortly after a config/secret/ConfigMap change
**Severi
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-005

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (Configuration Error)

**Alert:** Pod restart count > 5 within 10 minutes with exitCode=1 (application
startup failure), shortly after a config/secret/ConfigMap change
**Severi
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-K8S-2001

**Severity:** P3
**Root Cause:** Primary cause relates to: ## ImagePullBackOff

**Alert:** Pod stuck in ImagePullBackOff — image cannot be pulled
**Severity:** Medium
**Routing:** platformOnCall

**Impact:**
- New pods fail to start, capacity drops
- Deployme
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-010

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (OOMKilled)

**Alert:** Pod restart count > 5 within 10 minutes, termination reason
OOMKilled
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- Reduced service capa
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-K8S-4003

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (OOMKilled)

**Alert:** Pod restart count > 5 within 10 minutes, termination reason
OOMKilled
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- Reduced service capa
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-AVAIL-4001

**Severity:** P2
**Root Cause:** ## Service Availability Degradation (Traffic Spike)

**Alert:** Synthetic availability < 100% for a public endpoint, or request
rate > 3x the 7-day baseline with rising latency
**Severity:** Critical
**Routing:** prodCritical

**Impact:**
- Users see slow or failed page loads (503/504s)
- Availability SLO burn; potential revenue loss during campaigns
- Readiness-probe failures further reduce serving capacity

**RCA Path:**
1. Confirm the traffic-shape change: compare current request rate against the
   7-day baseline and check for campaign/marketplace events.
2. Check HPA behavior: desired vs. current replicas, stabilization windows,
   and how far scaling lagged behind demand.
3. Check saturation signals: CPU utilization, connect-queue depth, connection
   pools, and p99 latency trend.
4. Correlate readiness/liveness probe failures with the load peak.
5. Verify no concurrent deployment or configuration change coincided.

**Solution (recommendations — the on-call engineer applies the fix):**
- Scale up replicas manually to absorb the spike while the HPA catches up
  (or lower the HPA stabilization window / raise maxReplicas).
- Restart pods that are wedged by probe failures once capacity is in place.
- Add/verify upstream timeouts and load-shedding limits so queues drain
  instead of saturating.
- After the event, re-tune HPA parameters so reaction time matches the
  traffic-ramp shape.

---
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.750536322593689 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-010

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (OOMKilled)

**Alert:** Pod restart count > 5 within 10 minutes, termination reason
OOMKilled
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- Reduced service capa
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-010

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (OOMKilled)

**Alert:** Pod restart count > 5 within 10 minutes, termination reason
OOMKilled
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- Reduced service capa
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-010

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (OOMKilled)

**Alert:** Pod restart count > 5 within 10 minutes, termination reason
OOMKilled
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- Reduced service capa
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-010

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (OOMKilled)

**Alert:** Pod restart count > 5 within 10 minutes, termination reason
OOMKilled
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- Reduced service capa
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-K8S-2091

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (Configuration Error)

**Alert:** Pod restart count > 5 within 10 minutes with exitCode=1 (application
startup failure), shortly after a config/secret/ConfigMap change
**Severi
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-005

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (Configuration Error)

**Alert:** Pod restart count > 5 within 10 minutes with exitCode=1 (application
startup failure), shortly after a config/secret/ConfigMap change
**Severi
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-010

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (OOMKilled)

**Alert:** Pod restart count > 5 within 10 minutes, termination reason
OOMKilled
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- Reduced service capa
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-010

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (OOMKilled)

**Alert:** Pod restart count > 5 within 10 minutes, termination reason
OOMKilled
**Severity:** High
**Routing:** platformOnCall

**Impact:**
- Reduced service capa
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-K8S-2091

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (Configuration Error)

**Alert:** Pod restart count > 5 within 10 minutes with exitCode=1 (application
startup failure), shortly after a config/secret/ConfigMap change
**Severi
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-005

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Pod CrashLoopBackOff (Configuration Error)

**Alert:** Pod restart count > 5 within 10 minutes with exitCode=1 (application
startup failure), shortly after a config/secret/ConfigMap change
**Severi
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.
