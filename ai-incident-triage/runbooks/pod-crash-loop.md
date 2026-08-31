# Pod Crash Loop

## Overview
A workload's pods start, crash, and restart repeatedly (`CrashLoopBackOff`),
often with a `Back-off restarting failed container` event. Common causes:
application misconfiguration (missing env vars/config, e.g. a renamed secret
mount), the process being OOMKilled when it exceeds its memory limit, DB
connection failures on startup, or an uncaught exception during init.

## Solution
1. `kubectl logs <pod> --previous` to read the crashed container's last output.
2. `kubectl describe pod <pod>` and check the last `State`/`Reason` — confirm if
   the termination reason is `OOMKilled` (exit 137) or an application error.
3. If `OOMKilled`: check the memory trend (gradual climb = leak, sudden spike =
   traffic burst). Roll back to the last known-good image if deployment
   correlated; otherwise raise the memory limit as temporary mitigation and
   file a follow-up for the leak.
4. If config-related (missing secret/env): fix the ConfigMap/Secret reference and
   re-roll. For auth pods a renamed secret volume mount is a common trigger.
5. Confirm recovery: `ready` replicas return to `desired`, restart count
   stabilises, and error rate drops to baseline.

## Troubleshooting
- `CrashLoopBackOff` + `OOMKilled` + high restart count → memory pressure.
- `CrashLoopBackOff` immediately after a config deploy → misconfiguration; check
  the new ConfigMap/Secret/Helm values.
- Healthy-look `Restarting` pods with no OOM → check app startup logs for an
  uncaught init exception.
