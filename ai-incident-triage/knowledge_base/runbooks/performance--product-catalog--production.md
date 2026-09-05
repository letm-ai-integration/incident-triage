---
title: Intermittent HTTP 503 errors on product-catalog service
service: product-catalog
severity_applicable: [P2]
tags: ['product-catalog']
version: 1
last_reviewed: 2026-08-31
owning_team: auto-generated
---

# Intermittent HTTP 503 errors on product-catalog service

## Symptoms
- Customers intermittently receive HTTP 503 "Service Unavailable" pages on the web storefront.
- API gateway returns 503 for approximately 1 in 6 requests to the product-catalog service.
- Correlated with slow upstream response times from product-catalog and high JVM heap saturation.

## Diagnosis Steps
1. Check API gateway logs for 503 response patterns and correlation with product-catalog response times.
2. Examine product-catalog service metrics (CPU, memory, JVM heap usage, request latency, error rate).
3. Investigate JVM heap dumps or GC logs for memory leaks, excessive GC pauses, or full GC events.
4. Review upstream dependency health (database, caching, other services) for slow or failing responses.
5. Look for recent deployments, configuration changes, or traffic spikes that may have triggered the issue.
6. If heap saturation is confirmed, analyze heap usage to identify potential memory leaks or high object allocation.

## Resolution
1. **If heap saturation is caused by memory leak:** Restart the service and roll back any recent code changes. Then investigate and fix the leak in a non-production environment.
2. **If heap saturation is due to increased traffic:** Scale up the product-catalog service (increase JVM heap size, add more instances) or implement a circuit breaker to protect downstream callers.
3. **If slow upstream responses are the root cause:** Optimize slow queries, increase upstream capacity, or add caching. Consider timeouts and retry policies.
4. After applying the fix, monitor the service for 5-10 minutes to confirm error rate drops below 5% and heap usage stabilizes.
5. If the fix is not effective, escalate to the owning team for further investigation.

## Observed Incident — 2026-08-31 — INC-PERF-3077
**Severity:** P2
**Root Cause:** Primary cause relates to: ## HTTP 503 Service Unavailable

**Alert:** HTTP 503 responses exceeding 5% of request volume for 5 minutes
**Severity:** High
**Routing:** prodCritical

**Impact:**
- Downstream callers receive servi

**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.

## Observed Incident — 2026-08-31 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Diagnosis Steps

1. Check API gateway logs for 503 response patterns and correlation with product-catalog response times.
2. Examine product-catalog service metrics (CPU, memory, JVM heap usage, request latency, error rate).
3. Investigate JVM heap dumps or GC logs for memory leaks, excessive GC pauses, or full GC events.
4. Review upstream dependency health (database, caching, other services) for slow or failing responses.
5. Look for recent deployments, configuration changes, or traffic spikes that may have triggered the issue.
6. If heap saturation is confirmed, analyze heap usage to identify potential memory leaks or high object allocation.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8153234720230103 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Observed Incident — 2026-08-31 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Diagnosis Steps

1. Check API gateway logs for 503 response patterns and correlation with product-catalog response times.
2. Examine product-catalog service metrics (CPU, memory, JVM heap usage, request latency, error rate).
3. Investigate JVM heap dumps or GC logs for memory leaks, excessive GC pauses, or full GC events.
4. Review upstream dependency health (database, caching, other services) for slow or failing responses.
5. Look for recent deployments, configuration changes, or traffic spikes that may have triggered the issue.
6. If heap saturation is confirmed, analyze heap usage to identify potential memory leaks or high object allocation.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8153234720230103 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8209024667739868 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Observed Incident — 2026-08-31 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Diagnosis Steps

1. Check API gateway logs for 503 response patterns and correlation with product-catalog response times.
2. Examine product-catalog service metrics (CPU, memory, JVM heap usage, request latency, error rate).
3. Investigate JVM heap dumps or GC logs for memory leaks, excessive GC pauses, or full GC events.
4. Review upstream dependency health (database, caching, other services) for slow or failing responses.
5. Look for recent deployments, configuration changes, or traffic spikes that may have triggered the issue.
6. If heap saturation is confirmed, analyze heap usage to identify potential memory leaks or high object allocation.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8153234720230103 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8209024667739868 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Observed Incident — 2026-08-31 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Diagnosis Steps

1. Check API gateway logs for 503 response patterns and correlation with product-catalog response times.
2. Examine product-catalog service metrics (CPU, memory, JVM heap usage, request latency, error rate).
3. Investigate JVM heap dumps or GC logs for memory leaks, excessive GC pauses, or full GC events.
4. Review upstream dependency health (database, caching, other services) for slow or failing responses.
5. Look for recent deployments, configuration changes, or traffic spikes that may have triggered the issue.
6. If heap saturation is confirmed, analyze heap usage to identify potential memory leaks or high object allocation.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8153234720230103 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8209024667739868 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Observed Incident — 2026-08-31 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Diagnosis Steps

1. Check API gateway logs for 503 response patterns and correlation with product-catalog response times.
2. Examine product-catalog service metrics (CPU, memory, JVM heap usage, request latency, error rate).
3. Investigate JVM heap dumps or GC logs for memory leaks, excessive GC pauses, or full GC events.
4. Review upstream dependency health (database, caching, other services) for slow or failing responses.
5. Look for recent deployments, configuration changes, or traffic spikes that may have triggered the issue.
6. If heap saturation is confirmed, analyze heap usage to identify potential memory leaks or high object allocation.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8153234720230103 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8209024667739868 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Observed Incident — 2026-08-31 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Diagnosis Steps

1. Check API gateway logs for 503 response patterns and correlation with product-catalog response times.
2. Examine product-catalog service metrics (CPU, memory, JVM heap usage, request latency, error rate).
3. Investigate JVM heap dumps or GC logs for memory leaks, excessive GC pauses, or full GC events.
4. Review upstream dependency health (database, caching, other services) for slow or failing responses.
5. Look for recent deployments, configuration changes, or traffic spikes that may have triggered the issue.
6. If heap saturation is confirmed, analyze heap usage to identify potential memory leaks or high object allocation.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8153234720230103 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8209024667739868 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Observed Incident — 2026-08-31 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Diagnosis Steps

1. Check API gateway logs for 503 response patterns and correlation with product-catalog response times.
2. Examine product-catalog service metrics (CPU, memory, JVM heap usage, request latency, error rate).
3. Investigate JVM heap dumps or GC logs for memory leaks, excessive GC pauses, or full GC events.
4. Review upstream dependency health (database, caching, other services) for slow or failing responses.
5. Look for recent deployments, configuration changes, or traffic spikes that may have triggered the issue.
6. If heap saturation is confirmed, analyze heap usage to identify potential memory leaks or high object allocation.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8153234720230103 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8209024667739868 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Observed Incident — 2026-08-31 — INC-PERF-3077

**Severity:** P2
**Root Cause:** ## Diagnosis Steps

1. Check API gateway logs for 503 response patterns and correlation with product-catalog response times.
2. Examine product-catalog service metrics (CPU, memory, JVM heap usage, request latency, error rate).
3. Investigate JVM heap dumps or GC logs for memory leaks, excessive GC pauses, or full GC events.
4. Review upstream dependency health (database, caching, other services) for slow or failing responses.
5. Look for recent deployments, configuration changes, or traffic spikes that may have triggered the issue.
6. If heap saturation is confirmed, analyze heap usage to identify potential memory leaks or high object allocation.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8153234720230103 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.8209024667739868 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.
