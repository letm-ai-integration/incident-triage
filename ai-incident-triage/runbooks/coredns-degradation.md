# CoreDNS Degradation Remediation

## Overview
Internal DNS resolution starts failing intermittently (`UnknownHostException`,
retries, timeouts) because CoreDNS itself is degraded — high query latency,
unhealthy/restarting pods, or only a subset of replicas Ready. App-level
failures and CoreDNS pod events are time-correlated; the causal link is inferred
from that correlation.

## Solution
1. Check CoreDNS pod health cluster-wide.
2. Scale up CoreDNS replicas or restart the unhealthy pod(s).
3. Check for a recent NetworkPolicy/ConfigMap change around the incident window.
4. Ensure client-side DNS caching and connection retry/backoff are configured
   for internal clients.
5. Add an alert on CoreDNS readiness/query latency specifically.

## Troubleshooting
- `UnknownHostException` + `CoreDNSHighLatency`/unhealthy CoreDNS pod events →
   apply this runbook.
- `UnknownHostException` with healthy CoreDNS → application DNS config or
  upstream resolver; verify before scaling CoreDNS.