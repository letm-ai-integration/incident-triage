# Downstream Rate Limiting Remediation

## Overview
Elevated 5xx/502 responses on the caller surface because a downstream partner
API is rate-limiting traffic (a wave of `429 Too Many Requests`). The caller's
own traffic may be steady; the partner's effective limit dropped or was newly
enforced. Retrying hard surfaces a 502 instead of degrading gracefully.

## Solution
1. Confirm the 5xx spike correlates with 429s from a specific downstream
   partner via log/trace correlation.
2. Check the partner's status page/changelog for a recently lowered limit or
   ongoing incident.
3. Tighten client-side rate limiting and exponential backoff-with-jitter to
   stay under the partner's limit.
4. If supported, request a temporary limit increase or a dedicated higher-tier
   API key.
5. Add a circuit breaker so repeated 429s degrade gracefully instead of
   surfacing a hard 502.

## Troubleshooting
- `429` bursts from the partner + hard `502` after retry budget exhaustion →
  partner limit; throttle and open a circuit breaker.
- 5xx rise with no partner 429s → investigate internally; this runbook does not
  apply.