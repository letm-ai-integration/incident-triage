# Service Availability / Traffic Spike Remediation

## Overview
A sudden traffic increase exceeds current replica/connection capacity, so
availability drops, HTTP 503s rise and latency climbs while HPA scaling lags
behind demand. Reduced availability, elevated traffic, connection saturation
and delayed scaling are directly observed; a restart is not proven necessary and
timeouts alone would not have prevented this.

## Solution
1. Increase replicas/capacity to absorb sustained traffic above target.
2. Verify HPA target, cooldown, and scale-up speed against demand.
3. Validate connection limits and request timeouts after scaling.
4. Restart individual unhealthy pods only after confirming capacity is
   available.

## Troubleshooting
- `request_rate` above target + `connection pool exhausted`/`503` + HPA
  `currentReplicas < desiredReplicas` → scale out and re-check HPA.
- 503s with replicas already above demand → look elsewhere (dependencies,
  config); do not scale blindly.