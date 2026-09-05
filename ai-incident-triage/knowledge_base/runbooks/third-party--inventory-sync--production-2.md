---
title: Downstream API Rate Limiting causing Circuit Breaker Flapping and Elevated 5xx Errors
service: inventory-sync
severity_applicable: [P1]
tags: ['inventory-sync']
version: 1
last_reviewed: 2026-09-03
owning_team: auto-generated
---

# Downstream API Rate Limiting causing Circuit Breaker Flapping and Elevated 5xx Errors

## Symptoms

- Elevated 5xx errors on inventory-sync, strongly correlated with HTTP 429 responses from the downstream logistics-vendor-api.
- Circuit breaker flapping (opening/closing repeatedly) due to retries without effective backoff.
- Stock-sync jobs are falling behind, causing storefront inventory to go stale.
- Unwrapped 429s surfaced to callers as cascading 5xx errors.

## Diagnosis Steps

1. Check inventory-sync error rate in monitoring dashboard; filter by HTTP 5xx status codes.
2. Inspect downstream logistics-vendor-api response metrics; look for HTTP 429 rate limit responses.
3. Review circuit breaker state transitions in inventory-sync logs to confirm flapping pattern.
4. Verify retry logic configuration—confirm if exponential backoff is disabled or misconfigured.
5. Check stock-sync job lag and storefront inventory freshness metrics.
6. Confirm correlation between 429 spikes and 5xx error spikes using time-series graphs.

## Resolution

1. **Immediate mitigation:** Apply rate limiting on inventory-sync outbound requests to logistics-vendor-api. Configure a client-side rate limiter with a lower request-per-second limit matching the downstream API's documented cap.
2. **Enable proper circuit breaker:** Set the circuit breaker to half-open after failure threshold and enforce a minimum open duration (e.g., 30 seconds) to prevent flapping.
3. **Improve retry logic:** Implement exponential backoff with jitter for retries when receiving HTTP 429 responses. Maximum retries should be limited (e.g., 3 attempts).
4. **Surface 429s properly:** Map HTTP 429 responses to a dedicated client error (e.g., HTTP 503) internally to prevent cascading 5xx to callers, or log and skip gracefully.
5. **Notify downstream API provider** if sustained rate limits indicate capacity issues.

## Observed Incident — 2026-09-03 — INC-API-4004

**Severity:** P1
**Root Cause:** Primary cause relates to:
- Elevated 5xx errors on inventory-sync, strongly correlated with HTTP 429 responses from the downstream logistics-vendor-api.
- Circuit breaker flapping (opening/closing repeatedly) due to retries without effective backoff.

**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.