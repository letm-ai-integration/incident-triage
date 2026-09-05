---
title: Third-party payment gateway timeouts
service: payment-service
severity_applicable: [P1]
tags: ['payment-service']
version: 1
last_reviewed: 2026-09-02
owning_team: auto-generated
---

# Third-party payment gateway timeouts

## Symptoms

- Payment service HTTP 503 responses exceed 5% of total request volume.
- Elevated timeout and 5xx errors from the external payment gateway (`payment-gateway-external`).
- Payment service retry counters and circuit-breaker state transitions are triggered.
- Customers may experience failed or delayed payment transactions.

## Diagnosis Steps

1. Check the payment-service’s circuit-breaker status:  
   Retrieve the metrics endpoint (e.g., `/actuator/health` or `/metrics`) for `resilience4j.circuitbreaker.state` for the `payment-gateway-external` circuit breaker. A state of `OPEN` or `HALF_OPEN` indicates the gateway is degraded.

2. Inspect recent logs from payment-service for retry exhaustion and timeout exceptions:  
   Look for entries containing `RetryableException`, `TimeoutException`, or `CircuitBreakerRecordError`. Filter on `payment-gateway-external` and the last 15 minutes.

3. Verify third-party gateway health:  
   Use the provider’s status page or perform a synthetic health check (e.g., `curl -v --connect-timeout 5 https://payment-gateway-external/health`). If the gateway returns 5xx or times out, the issue is external.

4. Confirm that the upstream provider has resolved the issue:  
   Wait for a reduction in timeout errors from the gateway, or check incident communications from the provider. The service’s circuit breaker will transition to `HALF_OPEN` and eventually `CLOSED` after successful probes.

## Resolution

1. **If the external gateway is still degraded:**  
   - No immediate fix possible from the application side.  
   - Monitor the provider’s status and let the circuit breaker handle load shedding automatically.  
   - Consider manual override only if critical business logic requires bypassing the circuit breaker (not recommended).

2. **If the gateway has recovered but the circuit breaker remains OPEN:**  
   - The circuit breaker will automatically attempt a transition to `HALF_OPEN` after the configured wait duration (default 60 seconds).  
   - To force a reset, restart the payment-service pods (e.g., `kubectl rollout restart deployment/payment-service -n payments`).  
   - Alternatively, clear the circuit breaker state via the Actuator endpoint:  
     `POST /actuator/circuitbreakers?state=CLOSED` (requires appropriate security permissions).

3. **After recovery:**  
   - Verify that HTTP 503 rates drop below 1% and circuit breaker state returns to `CLOSED`.  
   - Confirm deferred charges are settled by the provider (check payment reconciliation logs).  
   - Update the runbook if any manual steps were required.

## Observed Incident — 2026-09-02 — INC-004

**Severity:** P1  
**Root Cause:** Primary cause relates to:

- Payment service HTTP 503 responses exceed 5% of total request volume.
- Elevated timeout and 5xx errors from the external payment gateway (`payment-gateway-external`).
- Payment service

**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.

## Observed Incident — 2026-09-02 — INC-004

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- Payment service HTTP 503 responses exceed 5% of total request volume.
- Elevated timeout and 5xx errors from the external payment gateway (`payment-gateway-external`).
- Payment service
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-004

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- Payment service HTTP 503 responses exceed 5% of total request volume.
- Elevated timeout and 5xx errors from the external payment gateway (`payment-gateway-external`).
- Payment service
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.


## Observed Incident — 2026-09-02 — INC-004

**Severity:** P1
**Root Cause:** Primary cause relates to: ## Symptoms

- Payment service HTTP 503 responses exceed 5% of total request volume.
- Elevated timeout and 5xx errors from the external payment gateway (`payment-gateway-external`).
- Payment service
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.
