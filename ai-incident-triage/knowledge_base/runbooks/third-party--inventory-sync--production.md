---
title: Downstream API Rate Limiting (HTTP 429) Handling for inventory-sync
service: inventory-sync
severity_applicable: [P1]
tags: ['inventory-sync']
version: 1
last_reviewed: 2026-09-02
owning_team: auto-generated
---

# Downstream API Rate Limiting (HTTP 429) Handling for inventory-sync

## Symptoms
- Elevated 5xx errors on inventory-sync, strongly correlated with HTTP 429 responses from the downstream logistics-vendor-api.
- Circuit breaker flapping (opening/closing repeatedly) due to excessive retries without effective backoff.
- Stock-sync jobs falling behind, leading to stale inventory data in the storefront.
- Unwrapped 429s surfaced to callers as cascading 5xx errors.

## Diagnosis Steps
1. **Confirm the downstream API is returning 429**  
   Check inventory-sync logs for `HTTP 429` responses from `logistics-vendor-api`. Example command:  
   `grep "429" /var/log/inventory-sync/current.log | grep logistics-vendor-api`
2. **Verify retry behavior**  
   Look for retry attempts in the logs. A high number of retries within a short window indicates missing/insufficient backoff.
3. **Inspect circuit breaker state**  
   Query the circuit breaker metrics (e.g., Prometheus metric `circuit_breaker_state`) for flapping patterns (open → half-open → closed repeatedly).
4. **Check current downstream rate limit headers**  
   Parse `X-RateLimit-Remaining` or `Retry-After` headers from the vendor API responses to understand the limit and reset time.
5. **Assess impact on stock-sync throughput**  
   Monitor stock-sync job completion rates and lag (e.g., from job queue metrics) to confirm backlog growth.

## Resolution
1. **Apply exponential backoff to retries**  
   - Update the retry logic to use exponential backoff with jitter (e.g., initial delay 1s, multiplier 2, max 60s).  
   - Respect the `Retry-After` header when present.  
   - Example configuration snippet:  
     ```yaml
     retry:
       max_attempts: 5
       base_delay: 1s
       max_delay: 60s
       backoff_factor: 2
       jitter: true
     ```
2. **Adjust circuit breaker settings**  
   - Increase the failure threshold to reduce flapping (e.g., from 5 to 10 failures in 30s).  
   - Set a longer cooldown period (e.g., 60s) before transitioning back to half-open.
3. **Request upstream rate limit increase (if possible)**  
   - Contact the logistics-vendor-api team to negotiate a higher quota or purchase a tier upgrade.
4. **Implement graceful degradation**  
   - When circuit breaker is open, return stale cached inventory instead of propagating errors.  
   - Queue stock-sync jobs for later replay.
5. **Monitor recovery**  
   - Watch 5xx error rate drop below 1% and stock-sync jobs clear the backlog. Use dashboard like `inventory-sync:error_rate` and `inventory-sync:stock_sync_lag`.

## Observed Incident — 2026-09-02 — INC-API-4004
**Severity:** P1
**Root Cause:** Downstream API Rate Limiting (HTTP 429)

**Alert:** Sustained 429 responses from a downstream/third-party API, or 5xx rate on the owning service > 5% correlated with 429s
**Severity:** High
**Routi** (unfinished field – ignored)
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.75 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.