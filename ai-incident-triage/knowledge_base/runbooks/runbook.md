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