---
title: Third-party payment gateway timeout handling
service: payment-service
severity_applicable: [P1]
tags: ['payment-service']
version: 1
last_reviewed: 2026-08-31
owning_team: auto-generated
---

# Third-party payment gateway timeout handling

## Symptoms
- Payment service HTTP 503 responses exceed 5% of total request volume.
- Elevated timeout and 5xx errors from the external payment gateway (`payment-gateway-external`).
- Payment service retry counters spike and circuit-breaker state transitions (open/closed) are observed.
- Deferred charges may accumulate pending provider recovery.

## Diagnosis Steps
1. Check the payment-service error rate dashboard for HTTP 503 percentage.
2. Validate the circuit-breaker state for `payment-gateway-external` using the service’s health endpoint or metrics.
3. Review upstream provider status (e.g., status page or direct monitoring) to confirm if the outage is external.
4. Correlate the timing of circuit-breaker transitions with the spike in timeouts/5xx.
5. Examine payment-service logs for `payment-gateway-external` response times and retry count.
6. If the provider reports recovery, verify that the circuit-breaker transitions to half-open or closed and new requests succeed.

## Resolution
- If the external provider is degraded:
  - Wait for provider recovery (passive).
  - Optionally, switch to a fallback gateway if configured.
  - Increase the circuit-breaker threshold or retry count only if safe and approved.
- If the provider has recovered but the circuit-breaker remains open:
  - Manually reset the circuit-breaker via admin endpoint.
  - Monitor initial requests for success.
- For deferred charges:
  - Trigger a batch settlement job once the gateway is healthy.
- Verify normal charge processing resumes and error rate drops below 5%.

## Observed Incident — 2026-08-31 — INC-004
**Severity:** P1
**Root Cause:** Primary cause relates to: ## Observed Incident — 2026-08-31 — INC-PERF-3077

**Severity:** P2
**Root Cause:** Primary cause relates to: ## HTTP 503 Service Unavailable

**Alert:** HTTP 503 responses exceeding 5% of request vol
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.