# Master Instructions: Evidence-Grounded Investigation Pipeline, Expanded Mock Data & Runbooks, Corrected Reporting

Work through this file **in phase order, top to bottom**. Do not skip ahead to mock data or the report template before Phases 1–4 are done — the later phases depend on the evidence/validation model built in the earlier ones, and doing them out of order is how you end up with two systems disagreeing with each other.

**Ground rules that apply to every phase below:**
- **Analyze before editing.** For every phase, read the actual existing code/data first. Do not assume field names, node names, or file locations — confirm them.
- **Additive only.** Do not delete, rewrite, or weaken anything already working: graph layout, live per-node status, active-node detail panel, sub-agent nesting, the legend, panel scrolling. If something existing conflicts with a rule below, bring it into sync rather than leaving two contradictory versions in the codebase.
- **No invented mock data.** Every new incident/log/runbook needed for this task is fully specified in Phase 6 below. Do not design your own incident scenarios — this task previously allowed that and it's exactly the wrong move given the accuracy rules you're also implementing; inventing data invites the same fabrication problem you're trying to eliminate elsewhere.
- Report back **only** the single word `FINISHED` once every item in the Phase 9 checklist is verified — not just implemented.

---

## PHASE 1 — Audit the existing pipeline end to end

Before writing any code, trace the full flow and identify exactly where each of the following is currently produced. Write your findings into `NOTES.md` (or extend it if it already exists from earlier work) — this is your source of truth for every later phase:

- incident input/normalization (ingestion)
- evidence collection (logs, k8s/metrics, other diagnostics)
- the log-analysis sub-agent
- the Kubernetes diagnostics sub-agent
- any other diagnostic sub-agents
- runbook retrieval/matching — **specifically, what file(s) or data store runbooks live in, and what field(s) the matching logic keys on** (this matters a lot for Phase 7)
- hypothesis generation
- RCA synthesis
- report/notification generation
- verification / resolution-state calculation

Also confirm, exactly:
- The real field names for `evidence`, `hypotheses`, `root_cause`, `confidence`, `investigation_status`, `is_resolved`, `recommended_actions`, and the notification/email text.
- The exact mock-data schema and log format used by the existing incidents (field names, nesting, JSON log shape) — every new incident and log in Phase 6 must match this exactly, not the simplified plain-text form some of them are shown in below (see the note in Phase 6).
- Do not assume an LLM-generated statement is evidence just because it's inside an `Evidence`-shaped object — trace where its underlying data actually came from.

---

## PHASE 2 — Evidence provenance & grounding model

Add an explicit provenance/type distinction to evidence and claims, without breaking the existing schema or its consumers (extend, don't replace; use the project's existing enum/model conventions rather than inventing a parallel abstraction).

At minimum, distinguish:

1. **OBSERVED** — directly supported by raw logs, metrics, traces, or Kubernetes state/events.
2. **REPORTED** — supplied by the incident/alert description or source system, not independently verified by telemetry.
3. **CONTEXT** — retrieved from a runbook/knowledge base; useful for remediation guidance, not proof the symptom occurred.
4. **INFERRED** — a conclusion derived by reasoning over other evidence.

**Critical rule: runbook content must never be treated as direct incident evidence.** A runbook symptom match tells you the runbook is *relevant*, not that the symptom actually happened.

### Evidence-availability guards

The system must never claim a source confirmed something it has no data for:
- `raw_logs=[]` (or empty) → never generate "log analysis confirms..." findings.
- `raw_metrics={}` (or empty) → never generate metric-confirmed findings.
- no Kubernetes events/status → never claim Kubernetes confirmed a condition.
- no traces → never claim trace-based confirmation.

When a source is unavailable, say so explicitly (e.g. "No raw log evidence was available for independent verification") rather than silently omitting the caveat. Specifically check for and fix any place in the existing agents where `log_count=0` (or an equivalent empty-result indicator) still produces a detailed "confirmed" finding — this is a known recurring bug, fix it at the code boundary so it can't recur for future incidents.

### Reported vs. verified

The incident description may already contain a detailed causal story — preserve it, but never silently upgrade it to independently observed telemetry:
- Incident says "vendor API returned HTTP 429" → **REPORTED**, unless independent logs confirm it.
- Actual logs show HTTP 429 → **OBSERVED**.
- Runbook describes 429 handling → **CONTEXT**.
- Agent concludes retry amplification likely caused cascading failures → **INFERRED**, and its confidence must be no higher than the evidence actually supports.

---

## PHASE 3 — Deterministic claim validation & confidence calibration

### Validation step before RCA finalization

Add a deterministic (code, not a second LLM call) validation step before the report/notification is generated. At minimum, detect and reject/downgrade:
- OOMKilled claims without an OOMKilled/exit-code-137/restart signal
- CrashLoopBackOff claims without matching Kubernetes state/events
- CPU saturation claims without CPU metrics
- "DB outage/unreachable" claims when the actual evidence only shows connection-pool exhaustion
- recovery claims without post-remediation recovery evidence
- any claim derived only from a runbook symptom section
- any claim generated from an empty log/metric/event source

If a claim can't be verified, downgrade its wording ("reported," "likely," "not independently verified," "telemetry unavailable") instead of presenting it as confirmed.

### Confidence calibration

Do not let confidence be an arbitrary number (e.g. `0.95`) when evidence is empty or mostly inferred:
- direct observed telemetry outweighs incident-description text
- multiple independent telemetry sources increase confidence
- runbook similarity increases **runbook relevance**, never RCA certainty directly
- missing telemetry reduces confidence
- contradictions sharply reduce confidence
- an inference can't have higher confidence than the evidence supporting it, without a clearly justified rule

If a confidence calculation already exists, extend it — don't build a second, competing one.

---

## PHASE 4 — Decouple confidence from resolution, and gate resolution on real evidence

**RCA confidence and resolution status are separate concepts and must never be conflated.** It is valid to have `RCA confidence: High` and `Resolution status: Remediation Pending` simultaneously. Never mark an incident resolved merely because confidence is high, a runbook match exists, or a recommended fix exists.

Because this application only investigates and recommends — it has no remediation executor — enforce this gate:

```
Fix applied by this system? NO
        ↓
Cannot be RESOLVED
        ↓
REMEDIATION_PENDING / INVESTIGATED / RCA_COMPLETED
```

Suggested state flow:
```
INVESTIGATING → RCA_IDENTIFIED → REMEDIATION_PENDING → EXTERNAL_FIX_APPLIED/FIX_REPORTED → RECOVERY_CHECK → RECOVERED → RESOLVED
```
`RESOLVED` requires explicit, externally-supplied evidence of recovery — never infer it from diagnosis alone. Do not build a remediation executor as part of this task; the investigate-only scope stays intact.

Useful recovery signals, if a future incident ever supplies them: error rate returning to baseline, 429/5xx rate decreasing, queue/waiting count normalizing, latency normalizing, pod restart/crash state clearing, memory/disk/CPU returning to safe range, readiness becoming healthy. Without such evidence, state stays non-resolved.

---

## PHASE 5 — Canonical report/notification template

The final report/notification must render into this exact structure (this replaces the current ad-hoc format, and directly fixes the "[Resolved]" / "Resolution steps taken" wording problem from the original screenshot):

```markdown
## Incident Summary

### Incident Overview
<Concise summary: affected service, triggering condition, observed failure, resulting impact. Minimum ~5 lines, distinguishing reported trigger from independently observed trigger when they differ.>

### Environment
- **Environment:** `<production / staging / development>`

### Impacted Services
| Service | Severity / Role | Impact |
| --- | --- | --- |
| `<service-name>` | `<severity / dependency>` | `<observed impact>` |

### Impact Assessment
<Technical/customer-facing impact actually observed — error behavior, delays, data freshness, etc.>

### Investigation Findings
- <Finding backed by monitoring/logs/metrics — every finding here must trace to a specific evidence item>
- <Finding about relevant service/dependency behavior>
- <Finding linking observed symptoms together>

### Root Cause Analysis
**Root Cause:** `<Confirmed root cause / Probable root cause / Root cause could not be conclusively determined>`
**Contributing Factors:** <secondary conditions, or "None identified">

### Recommended Remediation
**Runbook Status:** `<Applicable runbook found / No applicable runbook found>`

**When an Applicable Runbook Is Available:**
1. <Runbook step>
2. <Runbook step>

**When No Applicable Runbook Is Available:**
> **Runbook remediation unavailable:** No applicable runbook or validated remediation procedure was found. The investigation has identified the observed symptoms and available evidence, but a validated remediation path is not available. **On-call engineering action is required to determine, apply, and validate the appropriate fix.**

### Investigation Status
- **Investigation:** `<Completed / In Progress>`
- **Root-Cause Analysis:** `<Confirmed / Probable / Inconclusive>`
- **Remediation:** `<Not Applied / Applied / Pending On-Call Action>`

> **Important:** This investigation is limited to analysis and recommendation unless explicitly stated otherwise. No remediation should be considered applied unless there is evidence the change was actually executed and validated.
```

### Population rules — the template is a presentation contract, not a source of facts

1. Populate every field only from validated investigation state — never plausible guesses. Missing evidence → say explicitly it couldn't be established.
2. `Root Cause` uses exactly one of the three states shown; never anything looser.
3. `Contributing Factors` never contains a symptom dressed up as a cause — runbook symptoms are not contributing-factor evidence.
4. `Recommended Remediation` describes what *should* be done — never `fixed`, `remediated`, `restarted`, `scaled`, `increased`, or `resolved` unless there is explicit execution evidence.
5. `Remediation: Applied` requires an execution record *and* post-change validation evidence — otherwise `Not Applied` or `Pending On-Call Action`.
6. `Investigation: Completed` means the analysis workflow finished — it does **not** mean the incident is resolved. `Root-Cause Analysis: Confirmed` is independent of remediation status (a confirmed RCA can coexist with `Remediation: Not Applied`).
7. The report generator must **only render** the already-validated investigation result (Phases 2–4) — it must never independently invent or reinterpret the RCA. This is what prevents contradictions like "remediation is pending" and "the incident has been resolved" appearing in the same notification.
8. If evidence is genuinely insufficient, present that plainly (what's known / independently verified / reported-but-unverified / likely cause / what remains to be verified / recommended runbook action / current status) rather than fabricating a complete-looking RCA. A lower-confidence, honestly-uncertain report beats a confident wrong one.

---

## PHASE 6 — Mock data: fix the existing incident, then add new incidents (fully specified — implement as given)

### 6.1 Fix `INC-006` first

Using what you found in Phase 1, bring `INC-006`'s mock data, logs, runbook reference, and any cached/expected report output into consistency with Phases 1–5: it must never claim resolution, its logs/description/runbook must tell one consistent story, and any stale "resolved" wording anywhere tied to it must be corrected.

### 6.2 Format note — read before writing any new incident below

The incidents below are written in a **simplified log format for readability in this document**. Before implementing, convert every log line into the exact JSON schema you found in Phase 1 (the same fields used by the existing mock logs — `timestamp`, `sequence`, `loggerClassName`, `loggerName`, `level`, `message`, `threadName`, `threadId`, `mdc`, `processName`, `processId`, `IMAGE_TAG`, `region`, `environment`, or whatever the real field set turns out to be). Keep the same timestamps, messages, and metric values — only reformat the shape. Worked example, converting one line from Incident H below:

Simplified: `2026-09-04T10:14:32.118Z INFO  checkout-service request_rate=1480rpm replicas=6 target=900rpm`

Converted:
```json
{"timestamp":"2026-09-04T10:14:32.118Z","sequence":50101,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.checkoutservice.app.monitoring.TrafficMonitor","level":"INFO","message":"request_rate=1480rpm replicas=6 target=900rpm","threadName":"executor-thread-1","threadId":90,"mdc":{"affiliate_code":"001"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"7.3.0","region":"us-east-1","environment":"production"}
```
Apply this same conversion pattern to every log line in every incident below, keeping `sequence` numbers increasing within each incident.

### 6.3 Note on de-duplication

An earlier draft of this task specified an incident "Service Availability < 100% (traffic spike)" separately from Incident H below. **They are the same scenario.** Implement only **Incident H** (below) for the traffic-spike/availability case — it is the fully evidence-grounded version. Do not also implement a second near-duplicate availability incident for that mechanism.

### 6.4 The 11 new incidents (implement exactly as specified)

#### Incident B — Container High Memory Usage Alert
- **Incident ID:** `INC-MEM-5006` · **Service:** `content-service` · **Environment:** `staging` · **Priority:** P3
- **Tags:** `["memory", "resource-limit", "kubernetes"]`
- **Scenario:** Sustained memory usage sits at ~100% of the configured limit with no clear leak signature — the app is simply under-provisioned for steady-state load.
- **Logs (many lines in a short span; convert per 6.2):**
```
{"timestamp":"2026-08-31T12:27:17.727693Z","sequence":8217,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.contentservice.app.controllers.v2","level":"INFO","message":"getContentByUid stack=web, name=redirection_items","threadName":"executor-thread-2","threadId":102,"mdc":{"affiliate_code":"001"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"1.0.0","requestDuration":"142ms","region":"us-east-1","environment":"staging"}
{"timestamp":"2026-08-31T12:27:17.728181Z","sequence":8225,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.contentservice.app.locale.TenantLocaleContext","level":"INFO","message":"Supported contains normalized language","threadName":"executor-thread-2","threadId":102,"mdc":{"affiliate_code":"001"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"2.0.0","locale":"en-US","tenantId":"tenant-mock-42","environment":"staging"}
```
(Surround these with several more lines of the same style/volume so it reads as an actual burst — same service/thread/format, incrementing `sequence`.)
- **Metrics:** Memory limit `1 Gi (1.07 GB)` · Actual usage `~1.07 GB` · Headroom `≈0%`
- **Runbook:** `Container Memory Limit / Steady-State Under-Provisioning` — increase the memory limit with 20–30% headroom above steady-state:
```yaml
resources:
  requests:
    memory: "1Gi"
  limits:
    memory: "1.5Gi"   # or "2Gi" depending on spike behavior
```
- **Evidence boundary:** Metrics prove sustained near-limit usage. They do not by themselves prove a memory leak — no growth-over-time signal is present here, only flat saturation.

#### Incident C — Pod CrashLoopBackOff due to OOMKilled
- **Incident ID:** `INC-OOM-5007` · **Service:** `recommendation-service` · **Environment:** `production` · **Priority:** P2
- **Tags:** `["memory", "oomkilled", "crashloop", "kubernetes"]`
- **Scenario:** A batch job inside the pod spikes memory in short bursts, exceeding the container limit and triggering repeated OOM kills.
- **App logs:**
```
{"timestamp":"2026-08-31T14:02:11.114302Z","sequence":15320,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.recommendationservice.app.batch.ModelRefreshJob","level":"INFO","message":"Loaded candidate embedding matrix, shape=[482113,256]","threadName":"batch-worker-1","threadId":41,"mdc":{"affiliate_code":"001"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"3.4.1","region":"us-east-1","environment":"production"}
{"timestamp":"2026-08-31T14:02:42.881765Z","sequence":15334,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.recommendationservice.app.batch.ModelRefreshJob","level":"WARN","message":"GC pause exceeded 800ms during embedding matrix merge, heap usage at 92%","threadName":"batch-worker-1","threadId":41,"mdc":{"affiliate_code":"001"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"3.4.1","region":"us-east-1","environment":"production"}
{"timestamp":"2026-08-31T14:02:57.019442Z","sequence":15341,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.recommendationservice.app.batch.ModelRefreshJob","level":"ERROR","message":"OutOfMemoryError while allocating buffer for candidate scoring batch, requested=512MB","threadName":"batch-worker-1","threadId":41,"mdc":{"affiliate_code":"001"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"3.4.1","region":"us-east-1","environment":"production"}
```
- **k8s events:**
```
{"type":"Warning","reason":"OOMKilling","object":"pod/recommendation-service-7c9f8d4b6-x2vqk","message":"Memory cgroup out of memory: Killed process 1 (java) total-vm:4213212kB, anon-rss:2093456kB, file-rss:0kB, shmem-rss:0kB","timestamp":"2026-08-31T14:03:01Z"}
{"type":"Normal","reason":"Killing","object":"pod/recommendation-service-7c9f8d4b6-x2vqk","message":"Container recommendation-service failed liveness probe, will be restarted","timestamp":"2026-08-31T14:03:02Z"}
{"type":"Warning","reason":"BackOff","object":"pod/recommendation-service-7c9f8d4b6-x2vqk","message":"Back-off restarting failed container recommendation-service in pod recommendation-service-7c9f8d4b6-x2vqk_prod","timestamp":"2026-08-31T14:05:40Z"}
```
- **Metrics:** Restart count `6 in 12 min` · Exit code `137` · Memory limit `2Gi` · Peak usage before kill `2.05Gi`
- **Runbook:** `OOMKilled / CrashLoopBackOff Remediation`
  1. Confirm OOMKilled via `kubectl describe pod` (Last State: Terminated, Reason: OOMKilled, Exit Code: 137).
  2. Identify the specific job/process causing the burst (here, `ModelRefreshJob`).
  3. Short-term: raise the memory limit with headroom (2Gi → 3Gi).
  4. Medium-term: capture a heap dump on next OOM to find the actual spike source.
  5. Consider isolating the batch job into its own pod/CronJob with a separate resource envelope.
- **Evidence boundary:** OOMKilled event + exit code 137 directly prove the kill mechanism. They do not by themselves prove the batch job is the *only* contributor — treat that link as inferred/probable unless heap-dump evidence confirms it.

#### Incident D — Elevated 5xx errors from downstream API rate limiting
- **Incident ID:** `INC-RATELIMIT-5008` · **Service:** `payment-gateway-service` · **Environment:** `production` · **Priority:** P1
- **Tags:** `["5xx", "rate-limit", "downstream", "payment"]`
- **Logs:**
```
{"timestamp":"2026-08-31T09:14:02.221093Z","sequence":22011,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.paymentgateway.client.FraudCheckClient","level":"WARN","message":"Received 429 Too Many Requests from fraud-check-partner API, retry-after=5s","threadName":"executor-thread-7","threadId":210,"mdc":{"affiliate_code":"003"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"5.2.0","region":"us-east-1","environment":"production"}
{"timestamp":"2026-08-31T09:14:07.552310Z","sequence":22019,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.paymentgateway.client.FraudCheckClient","level":"WARN","message":"Received 429 Too Many Requests from fraud-check-partner API, retry-after=5s","threadName":"executor-thread-7","threadId":210,"mdc":{"affiliate_code":"003"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"5.2.0","region":"us-east-1","environment":"production"}
{"timestamp":"2026-08-31T09:14:13.004421Z","sequence":22031,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.paymentgateway.app.controllers.CheckoutController","level":"ERROR","message":"Payment authorization failed after 3 retries: upstream fraud-check-partner API exhausted retry budget","threadName":"executor-thread-7","threadId":210,"mdc":{"affiliate_code":"003"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"5.2.0","region":"us-east-1","environment":"production","httpStatus":502}
{"timestamp":"2026-08-31T09:14:13.009554Z","sequence":22032,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.paymentgateway.app.controllers.CheckoutController","level":"ERROR","message":"Returning 502 Bad Gateway to client for order checkout","threadName":"executor-thread-7","threadId":210,"mdc":{"affiliate_code":"003"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"5.2.0","region":"us-east-1","environment":"production","httpStatus":502}
```
- **Metrics:** 5xx rate `0.2%→18.7%` over 6 min · fraud-check-partner 429 rate `64%` of calls · retry-budget exhaustion `340` events in 10 min · our traffic held steady at `~145 req/s` against the partner's newly-enforced `100 req/s` limit
- **Runbook:** `Downstream Rate Limiting Remediation`
  1. Confirm the 5xx spike correlates with 429s from a specific downstream partner via log/trace correlation.
  2. Check the partner's status page/changelog for a recently lowered limit or ongoing incident.
  3. Tighten client-side rate limiting and exponential backoff-with-jitter to stay under the partner's limit.
  4. If supported, request a temporary limit increase or a dedicated higher-tier API key.
  5. Add a circuit breaker so repeated 429s degrade gracefully instead of surfacing a hard 502.
- **Evidence boundary:** Logs directly prove 429s and our resulting 502s. Whether the partner's limit was actually lowered (vs. our traffic actually increasing) should be marked REPORTED/INFERRED unless the partner's changelog is independently checked.

#### Incident E — DNS resolution failures causing intermittent service timeouts
- **Incident ID:** `INC-DNS-5009` · **Service:** `inventory-service` · **Environment:** `production` · **Priority:** P2
- **Tags:** `["dns", "timeout", "networking", "intermittent"]`
- **App logs:**
```
{"timestamp":"2026-08-31T03:41:09.884213Z","sequence":9901,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.inventoryservice.client.WarehouseApiClient","level":"ERROR","message":"java.net.UnknownHostException: warehouse-api.internal.mockcorp.svc.cluster.local: Name or service not known","threadName":"executor-thread-3","threadId":88,"mdc":{"affiliate_code":"002"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"4.1.7","region":"us-east-1","environment":"production"}
{"timestamp":"2026-08-31T03:41:09.912440Z","sequence":9902,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.inventoryservice.client.WarehouseApiClient","level":"WARN","message":"DNS lookup retry 1/3 for warehouse-api.internal.mockcorp.svc.cluster.local","threadName":"executor-thread-3","threadId":88,"mdc":{"affiliate_code":"002"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"4.1.7","region":"us-east-1","environment":"production"}
{"timestamp":"2026-08-31T03:41:12.230981Z","sequence":9910,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.inventoryservice.client.WarehouseApiClient","level":"ERROR","message":"DNS lookup failed after 3 retries, request timed out at 3000ms","threadName":"executor-thread-3","threadId":88,"mdc":{"affiliate_code":"002"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"4.1.7","region":"us-east-1","environment":"production"}
```
- **Cluster indicators:**
```
{"type":"Warning","reason":"CoreDNSHighLatency","object":"deployment/coredns","message":"CoreDNS pod coredns-6d4b75cb6d-8xqzp p99 query latency 4200ms, exceeding 2000ms threshold","timestamp":"2026-08-31T03:40:55Z"}
{"type":"Warning","reason":"Unhealthy","object":"pod/coredns-6d4b75cb6d-8xqzp","message":"Readiness probe failed: dial tcp: connect: connection refused","timestamp":"2026-08-31T03:41:02Z"}
```
- **Metrics:** ~12% of inventory-service→warehouse-api calls failed intermittently `03:38–03:52 UTC` · CoreDNS `2/3` pods ready (1 in CrashLoopBackOff)
- **Runbook:** `CoreDNS Degradation Remediation`
  1. Check CoreDNS pod health cluster-wide.
  2. Scale up CoreDNS replicas or restart the unhealthy pod(s).
  3. Check for a recent NetworkPolicy/ConfigMap change around the incident window.
  4. Ensure client-side DNS caching and connection retry/backoff are configured for internal clients.
  5. Add an alert on CoreDNS readiness/query latency specifically.
- **Evidence boundary:** CoreDNS pod-health events and app-level DNS failures are both directly observed and time-correlated. The causal *link between them* (CoreDNS degradation → app failures) is INFERRED from correlation, not independently proven by a single trace.

#### Incident F — Disk space exhaustion on a persistent volume
- **Incident ID:** `INC-DISK-5010` · **Service:** `order-history-service` · **Environment:** `production` · **Priority:** P2
- **Tags:** `["disk", "storage", "pvc", "database"]`
- **App logs:**
```
{"timestamp":"2026-08-31T20:05:44.552198Z","sequence":30411,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.orderhistoryservice.app.repository.OrderWriteRepository","level":"ERROR","message":"could not write to file \"pg_wal/000000010000000000000042\": No space left on device","threadName":"executor-thread-4","threadId":57,"mdc":{"affiliate_code":"001"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"2.9.3","region":"us-east-1","environment":"production"}
{"timestamp":"2026-08-31T20:05:44.601872Z","sequence":30412,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.orderhistoryservice.app.repository.OrderWriteRepository","level":"ERROR","message":"PANIC: could not write to log file due to insufficient disk space, database entering read-only recovery mode","threadName":"executor-thread-4","threadId":57,"mdc":{"affiliate_code":"001"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"2.9.3","region":"us-east-1","environment":"production"}
```
- **k8s events:**
```
{"type":"Warning","reason":"FreeDiskSpaceFailed","object":"persistentvolumeclaim/order-history-pg-data","message":"Volume usage at 99.4% of 100Gi capacity","timestamp":"2026-08-31T20:04:30Z"}
```
- **Metrics:** PVC `100Gi`, used `99.4Gi (99.4%)` · growth `~2.1Gi/day` over trailing 14 days, mostly WAL retention + an unpruned `audit_log` table
- **Runbook:** `Disk Space Exhaustion Remediation`
  1. Confirm free space on the affected PVC.
  2. Immediate: prune/archive oldest `audit_log` partitions and clear already-shipped WAL segments.
  3. Expand the PVC if the storage class supports online expansion.
  4. Root-cause fix: add retention/partitioning on the unbounded-growth table.
  5. Add disk-usage alerts at 80%/90% thresholds.
- **Evidence boundary:** The 99.4% usage figure and write failures are directly observed. The `audit_log` growth attribution is INFERRED from a 14-day trend, not independently isolated by a per-table breakdown here.

#### Incident G — Cache stampede after a Redis eviction/restart
- **Incident ID:** `INC-CACHE-5011` · **Service:** `product-catalog-service` · **Environment:** `production` · **Priority:** P2
- **Tags:** `["cache", "redis", "stampede", "latency"]`
- **App logs:**
```
{"timestamp":"2026-08-31T11:00:02.001884Z","sequence":41022,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.productcatalogservice.cache.RedisCacheClient","level":"WARN","message":"Redis connection reset, client reconnecting to redis-catalog-cache-0.redis-catalog-cache-headless","threadName":"executor-thread-9","threadId":133,"mdc":{"affiliate_code":"001"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"6.0.2","region":"us-east-1","environment":"production"}
{"timestamp":"2026-08-31T11:00:03.442190Z","sequence":41030,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.productcatalogservice.cache.RedisCacheClient","level":"WARN","message":"Cache MISS rate jumped to 96% (baseline 4%), Redis dataset reports 0 keys post-restart","threadName":"executor-thread-9","threadId":133,"mdc":{"affiliate_code":"001"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"6.0.2","region":"us-east-1","environment":"production"}
{"timestamp":"2026-08-31T11:00:04.117832Z","sequence":41041,"loggerClassName":"org.slf4j.impl.Slf4jLogger","loggerName":"com.mockcorp.commerce.productcatalogservice.app.repository.ProductReadRepository","level":"ERROR","message":"Postgres connection pool exhausted: 100/100 connections in use, 210 requests queued","threadName":"executor-thread-9","threadId":133,"mdc":{"affiliate_code":"001"},"processName":"/work/quarkus/application","processId":1,"IMAGE_TAG":"6.0.2","region":"us-east-1","environment":"production"}
```
- **k8s events:**
```
{"type":"Normal","reason":"Killing","object":"pod/redis-catalog-cache-0","message":"Redis pod restarted due to node drain during scheduled maintenance","timestamp":"2026-08-31T11:00:00Z"}
```
- **Metrics:** Cache hit rate `96%→4%` for ~90s post-restart · DB read QPS `~800/s→~11,400/s` · Postgres pool exhausted (100/100) for ~40s · p95 latency `80ms→4.8s`
- **Runbook:** `Cache Stampede Remediation`
  1. Confirm timing correlation between the Redis restart and the DB load spike.
  2. If recurring, implement cache warm-up on Redis startup for high-traffic keys.
  3. Add request coalescing/single-flight locking so concurrent misses for the same key trigger one DB read.
  4. Add jittered TTL stagger on cache writes.
  5. Consider a Redis replica/failover topology.
- **Evidence boundary:** The restart→load-spike timing correlation is directly observed in the logs/events. The claim that this specific mechanism (vs. some other cause) is fully responsible remains a well-supported but INFERRED conclusion.

#### Incident H — Service Availability Below 100% During Traffic Spike
*(supersedes the earlier "Incident A" — implement this one only)*
- **Incident ID:** `INC-AVAIL-5001` · **Service:** `checkout-service` · **Environment:** `production` · **Priority:** P1
- **Scenario:** A sudden traffic increase exceeds current replica/connection capacity; availability drops while HPA scaling lags behind.
- **Incident timestamp:** `2026-09-04T10:15:00Z`
- **Logs (convert to JSON per 6.2):**
```
2026-09-04T10:14:32.118Z INFO  checkout-service request_rate=1480rpm replicas=6 target=900rpm
2026-09-04T10:14:48.402Z WARN  checkout-service request_queue_depth=186 active_connections=498 max_connections=500
2026-09-04T10:14:57.921Z WARN  checkout-service readiness probe latency=2.8s threshold=2s pod=checkout-service-7f8d9c6d7b-k2m4p
2026-09-04T10:15:03.107Z WARN  hpa/checkout-service desiredReplicas=10 currentReplicas=6 reason=cpu-utilization-above-target
2026-09-04T10:15:07.441Z ERROR checkout-service upstream request rejected status=503 reason="connection pool exhausted"
2026-09-04T10:15:12.883Z WARN  checkout-service readiness probe failed consecutiveFailures=3 pod=checkout-service-7f8d9c6d7b-p9x7q
2026-09-04T10:15:20.204Z INFO  hpa/checkout-service scaling currentReplicas=6 desiredReplicas=10
2026-09-04T10:15:41.516Z ERROR ingress checkout-service status=503 upstream_response_time=5.12s
2026-09-04T10:16:03.721Z INFO  checkout-service request_rate=2310rpm replicas=8 availability=98.7%
```
- **Metrics:** Availability `98.7%` at peak · request rate `2310rpm` vs. baseline `~1400rpm` · replicas `6→8`, desired `10` · active connections `498/500` · HTTP 503 rate `2.1%` · p95 latency `4.9s`
- **Runbook:** `Service Availability / Traffic Spike Remediation`
  1. Increase replicas/capacity to absorb sustained traffic above target.
  2. Verify HPA target, cooldown, and scale-up speed against demand.
  3. Validate connection limits and request timeouts after scaling.
  4. Restart individual unhealthy pods only after confirming capacity is available.
- **Evidence boundary:** Reduced availability, elevated traffic, connection saturation, and delayed scaling are directly observed. It is not proven that a restart is required or that timeouts alone would have prevented this.

#### Incident I — Kafka Consumer Lag / Delayed Processing
- **Incident ID:** `INC-KAFKA-5002` · **Service:** `order-event-consumer` · **Environment:** `production` · **Priority:** P2
- **Incident timestamp:** `2026-09-04T14:32:00Z`
- **Logs:**
```
2026-09-04T14:31:41.220Z INFO  order-event-consumer partition=3 pollBatch=500 processingTime=1840ms
2026-09-04T14:31:52.904Z WARN  order-event-consumer partition=3 processingTime=2670ms threshold=2000ms
2026-09-04T14:32:03.117Z WARN  kafka consumer_group=order-events groupLag=18420 partition=3
2026-09-04T14:32:19.481Z ERROR order-event-consumer message processing timeout orderId=ORD-78421 elapsed=5.04s
2026-09-04T14:32:31.605Z WARN  kafka consumer_group=order-events groupLag=24180 partition=3
2026-09-04T14:33:02.301Z WARN  order-event-consumer throughput=112msg/s producerRate=286msg/s
2026-09-04T14:33:26.904Z ERROR order-event-consumer commit delayed partition=3 reason="processing batch exceeded max.poll.interval"
```
- **Metrics:** Consumer lag `24,180 msgs` · producer rate `286 msg/s` · consumer throughput `112 msg/s` · processing latency `2.6–5.0s` · affected partition `3` · pod restarts `0`
- **Runbook:** `Kafka Consumer Lag Remediation`
  1. Identify whether processing latency or insufficient parallelism is the limiting factor.
  2. Scale consumers where partitioning allows.
  3. Review `max.poll.interval.ms` and batch size against measured processing time.
  4. Monitor lag/throughput after the change.
- **Evidence boundary:** Lag and throughput imbalance are directly observed. It is not proven that adding consumers alone resolves it if processing-time-per-message is the true bottleneck.

#### Incident J — Database Deadlock Causing Transaction Failures
- **Incident ID:** `INC-DB-5003` · **Service:** `payment-service` · **Environment:** `production` · **Priority:** P1
- **Incident timestamp:** `2026-09-04T16:48:00Z`
- **Logs:**
```
2026-09-04T16:47:42.104Z INFO  payment-service transaction=tx-81244 status=BEGIN account=ACC-2201
2026-09-04T16:47:42.441Z INFO  payment-service transaction=tx-81245 status=BEGIN account=ACC-2202
2026-09-04T16:47:43.006Z ERROR postgres deadlock detected transaction=tx-81244
2026-09-04T16:47:43.011Z WARN  payment-service transaction=tx-81244 rollback reason="deadlock detected"
2026-09-04T16:47:43.287Z ERROR postgres deadlock detected transaction=tx-81245
2026-09-04T16:47:43.294Z WARN  payment-service transaction=tx-81245 rollback reason="deadlock detected"
2026-09-04T16:47:44.102Z INFO  payment-service retry transaction=tx-81244 attempt=2 backoff=250ms
2026-09-04T16:48:05.721Z WARN  payment-service transaction_error_rate=3.8% baseline=0.2%
```
- **Metrics:** Deadlocks `37/5min` · transaction error rate `3.8%` vs baseline `0.2%` · DB CPU `61%` · DB connections `72/150` · app pod restarts `0`
- **Runbook:** `Database Deadlock Remediation`
  1. Capture deadlock details and identify the conflicting transaction/lock order.
  2. Standardize lock acquisition order where applicable.
  3. Keep transactions short; avoid unnecessary lock duration.
  4. Validate deadlock frequency/error rate after the change.
- **Evidence boundary:** Deadlocks and rollbacks are directly observed in logs. The exact application code path responsible for lock-order inversion is not proven here and should be marked as requiring further verification.

#### Incident K — TLS Certificate Expiration Causing Upstream Connection Failures
- **Incident ID:** `INC-TLS-5004` · **Service:** `notification-service` · **Environment:** `production` · **Priority:** P2
- **Incident timestamp:** `2026-09-04T18:21:00Z`
- **Logs:**
```
2026-09-04T18:20:51.781Z INFO  notification-service provider=messaging-gateway request=sendNotification
2026-09-04T18:20:52.019Z ERROR notification-service TLS handshake failed host=messaging-gateway reason="certificate has expired"
2026-09-04T18:20:52.021Z WARN  notification-service provider_response=UNAVAILABLE retryAttempt=1
2026-09-04T18:20:53.488Z ERROR notification-service outbound request failed exception=SSLHandshakeException
2026-09-04T18:21:07.904Z ERROR notification-service notification_delivery_failed reason="TLS certificate validation failed"
2026-09-04T18:21:24.115Z INFO  notification-service internal_healthcheck status=UP
```
- **Metrics:** TLS handshake failures `94/10min` · delivery failures `7.2%` · internal service health `UP` · provider `messaging-gateway` · cert expiry `2026-09-04T18:00:00Z`
- **Runbook:** `TLS Certificate Expiration Remediation`
  1. Confirm certificate chain and expiry on the affected endpoint.
  2. Renew/replace the expired certificate via the approved cert-management process.
  3. Reload/redeploy the affected TLS client config if required.
  4. Validate successful handshakes and delivery after the change.
- **Evidence boundary:** Certificate expiry and handshake failures are directly observed. Do not claim the certificate was replaced unless execution evidence exists.

#### Incident L — Service Availability Degradation from Readiness Probe Misconfiguration
*(distinct mechanism from Incident H — readiness config, not capacity — keep both)*
- **Incident ID:** `INC-AVAIL-5005` · **Service:** `search-service` · **Environment:** `staging` · **Priority:** P2
- **Incident timestamp:** `2026-09-04T20:05:00Z`
- **Logs:**
```
2026-09-04T20:04:41.022Z INFO  search-service startup completed elapsed=31s
2026-09-04T20:04:43.601Z WARN  kubelet pod=search-service-6c7d8f9f5b-r4n2m readiness probe failed path=/ready timeout=1s
2026-09-04T20:04:45.882Z WARN  kubelet pod=search-service-6c7d8f9f5b-r4n2m container=search-service reason="Readiness probe timeout"
2026-09-04T20:04:49.117Z INFO  search-service readiness endpoint response=200 elapsed=1.8s
2026-09-04T20:04:51.443Z WARN  kubelet pod=search-service-6c7d8f9f5b-k8w1q readiness probe failed path=/ready timeout=1s
2026-09-04T20:05:02.704Z ERROR ingress search-service status=503 upstream="no ready endpoints"
2026-09-04T20:05:18.312Z INFO  search-service process_status=RUNNING ready_endpoint=200
```
- **Metrics:** Available replicas `2/4` · ready replicas `2/4` · availability `99.1%` · readiness timeout `1s` vs actual response `1.8s` · pod restart count `0` (negative control — process never crashed) · 503 rate `0.9%`
- **Runbook:** `Readiness Probe Misconfiguration Remediation`
  1. Verify readiness timeout/initial-delay/failure-threshold against measured readiness latency.
  2. Adjust probe configuration to tolerate the validated latency.
  3. Roll out via the normal deployment process.
  4. Confirm all replicas become Ready and re-check availability/503 metrics.
- **Evidence boundary:** Readiness timeouts and reduced ready-endpoint count are directly observed. Restart count of `0` proves the process itself never crashed — do not claim a restart is necessary; this is exactly the kind of healthy/non-causal indicator (Phase 8) that must not be treated as a cause.

---

## PHASE 7 — Create matching runbook files (new deliverable — do not skip)

Each of the 11 incidents above must be backed by an actual **standalone runbook entry**, in whatever format/location Phase 1 revealed for the existing runbook(s) (e.g. `runbooks/Database Connection Failure`) — not just prose embedded inside the incident's own description. Create one runbook file per incident using the exact name given above (e.g. `runbooks/Container Memory Limit`, `runbooks/OOMKilled CrashLoopBackOff Remediation`, `runbooks/Downstream Rate Limiting Remediation`, `runbooks/CoreDNS Degradation Remediation`, `runbooks/Disk Space Exhaustion Remediation`, `runbooks/Cache Stampede Remediation`, `runbooks/Service Availability Traffic Spike Remediation`, `runbooks/Kafka Consumer Lag Remediation`, `runbooks/Database Deadlock Remediation`, `runbooks/TLS Certificate Expiration Remediation`, `runbooks/Readiness Probe Misconfiguration Remediation`), containing the "Runbook" numbered steps given for that incident above, formatted the same way the existing runbook file is formatted. Confirm the investigation/classification agent's runbook-matching logic can actually retrieve each new file by whatever key it matches on (title, tags, symptom keywords, etc. — from Phase 1).

---

## PHASE 8 — Apply grounding rules to every incident (`INC-006` + B–L)

1. Every causal claim gets an explicit `OBSERVED` / `REPORTED` / `CONTEXT` / `INFERRED` category wherever the schema allows (add a field if it doesn't exist yet, without breaking existing consumers).
2. Reported incident-description text stays `REPORTED` unless metrics/logs independently corroborate it.
3. Logs/metrics/k8s events must be incident-scoped: match on incident ID, service, environment, namespace/component, and timestamp window. Never let one incident's evidence leak into another's RCA (e.g. `checkout-service` CPU data must never become evidence for `product-catalog-service`, and OOMKilled evidence from Incident C must never be reused for Incident B).
4. Don't manufacture corroboration — if only one source proves a fact, don't present it as multi-source confirmed.
5. Runbook instructions never become evidence ("increase memory" does not prove memory was high; "restart pods" does not prove pods restarted).
6. Empty telemetry is meaningful and must be represented as missing evidence, not successful analysis.
7. Kubernetes health must reflect actual state — `Running` pods with only `Normal` events must never automatically become `degraded=True` (see Incident L's restart-count-`0` negative control).
8. None of these 12 incidents get `is_resolved=true`/`RESOLVED`/completed-fix wording — they are all investigation/recommendation scenarios by design.
9. Timestamps must stay within each incident's own window — never combine an incident's timestamp with another incident's logs or a different date's metrics; if timestamps don't align, flag the evidence as unrelated rather than using it.
10. Add automated validation for the mock dataset itself: unique incident IDs, service/environment consistency, timestamp-window consistency, required fields present, non-empty telemetry where the scenario says telemetry exists, valid runbook references, and no accidental cross-incident references.

---

## PHASE 9 — Regression tests

Add focused tests/fixtures (using the project's existing testing conventions) for at least:
1. Empty logs must not produce "log analysis confirms..." evidence.
2. Empty metrics must not produce metric-confirmed claims.
3. Runbook symptom matching must not become OBSERVED evidence.
4. High RCA confidence must not set `is_resolved=True`.
5. No fix applied + no recovery evidence → non-resolved state.
6. OOMKilled claim requires matching Kubernetes evidence (Incident C).
7. CPU/traffic saturation claim requires matching metrics (Incident H).
8. Evidence from another incident/service/time window must not be used (e.g. B vs. C memory evidence).
9. Incident-description facts stay distinguishable from telemetry-observed facts.
10. A remediation-pending notification never says "resolved" or implies a fix was applied.
11. "Recommended Remediation" contains recommendations, not completed actions.
12. A `RESOLVED` state can only be produced with explicit recovery evidence.
13. Restart-count-`0` (Incident L) must not be misread as evidence of instability.
14. Existing graph/live-status/sub-agent/legend/scrolling behavior still works after this refactor.

Prefer small deterministic unit tests around the validation logic, plus at least one end-to-end fixture per new incident using the mock pipeline.

---

## PHASE 10 — Sub-agent parallelism (documentation only, no code change)

Trace exactly how the `investigation` node invokes its sub-agents (k8s diagnostics, log analysis, etc.) and determine — using actual `await`/thread-pool/concurrency evidence, or empirically via `agent_trace` `started_at`/`ended_at` overlap from a real run, not just visual code structure — whether they run in parallel or sequentially. Write the finding to `NOTES.md` or `PARALLELISM_NOTES.md` with the evidence you checked. Do not change this behavior unless it's a trivial, clearly-safe fix — this is for a future decision, not to be silently altered here.

---

## MASTER VERIFICATION CHECKLIST (single source of truth — verify by running things, not by reading your own diff)

**Language & template**
- [ ] No generated report/notification ever says "resolved" or implies this system applied a fix.
- [ ] The canonical `Incident Summary` template (Phase 5) is what actually renders, with all its headings and status-field semantics intact.
- [ ] The "What happened"/`Incident Overview` narrative is ≥5 lines and genuinely explains the causal chain for every incident.

**Evidence & validation**
- [ ] Every evidence item has clear `OBSERVED`/`REPORTED`/`CONTEXT`/`INFERRED` provenance.
- [ ] Empty telemetry cannot produce a confirmed finding (test this against at least one incident with an intentionally empty source).
- [ ] Runbook matches are never treated as direct evidence.
- [ ] RCA confidence and resolution status vary independently — confirm at least one case where confidence is high but remediation is still `Not Applied`.
- [ ] `RESOLVED` is unreachable without explicit recovery evidence.
- [ ] Cross-incident/service/time-window contamination is prevented — confirm with a test that tries to leak evidence between two incidents.

**Mock data & runbooks**
- [ ] `INC-006` no longer claims resolution and is internally consistent.
- [ ] Incidents B–L (11 total) exist, schema-matched to the real repo format from Phase 1, each with logs, indicators, and a matching standalone runbook file from Phase 7.
- [ ] The old separate "traffic spike / Incident A" was NOT duplicated alongside Incident H.
- [ ] None of B–L claim resolution.
- [ ] The runbook-matching logic actually retrieves each new runbook file for its corresponding incident.

**Regression & existing functionality**
- [ ] All Phase 9 regression tests exist and pass.
- [ ] `NOTES.md`/`PARALLELISM_NOTES.md` documents the sub-agent concurrency finding with evidence.
- [ ] Graph layout, live per-node status, active-node detail panel, sub-agent nesting, the legend, and panel scrolling all still work, unchanged.

**Final validation**
- [ ] You actually ran the pipeline against `INC-006` and each of B–L and inspected the real generated report for each — evidence provenance, unsupported claims, contradictions, cross-incident contamination, confidence, resolution status, and recommended-vs-completed wording — not just re-read your source diff.

When every item above is genuinely verified — not merely implemented — report back exactly:

`FINISHED`