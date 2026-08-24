# INC-004: Third-Party API Timeout — Answer Key

**Actual root cause:** Degradation of the external provider
payment-gateway-external (provider status-page feed confirms "elevated error
rates"). Connect/TLS timeouts and 504/503 responses from the gateway caused
payment-service charge failures; the internal circuit breaker tracked the
outage and recovered when the provider did.

**Correct investigation trail:**
1. external_api_logs: outbound calls show TIMEOUT/HTTP_5XX/TLS_HANDSHAKE_TIMEOUT
   starting 10:31, with intermittent successes; provider feed at 10:35.
2. App logs (logs_traces, trace family `deadbeef*`): retry exhaustion, then
   CircuitBreaker OPEN (10:35) -> HALF_OPEN probe (10:43) -> failed probe
   (10:44) -> CLOSED (10:48). The breaker timeline corroborates, but alone
   doesn't identify *which* dependency or why.
3. Metrics: `egress_p95_latency_ms` 850 -> 9800; `payment_success_rate_pct`
   dips to 64.5 and recovers.

**Contributing factors:** retry amplification briefly deepened latency.
**Primary vs. secondary:** the external log is the primary evidence; app logs
and egress metrics are corroborating; kubernetes and deployment sources have
no signal (by design — agents should stay quiet there).
**Red herrings present:** successful charges interleaved mid-outage (partial
recovery); notification-service slow email; a 404 on /api/v1/products.
**Expected resolution:** rely on circuit breaker/fallback queuing until the
provider recovers; settle deferred charges afterward (no local fix applies).
