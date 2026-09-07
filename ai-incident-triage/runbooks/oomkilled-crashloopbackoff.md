# OOMKilled / CrashLoopBackOff Remediation

## Overview
A pod is repeatedly terminated by the kubelet with `OOMKilled` and entering
CrashLoopBackOff. A bursty job inside the container (batch refresh, large
allocations) exceeds the memory limit and gets exit code 137. The OOMKilled
event plus exit 137 prove the kill mechanism; what spiked memory may still need
heap-dump confirmation.

## Solution
1. Confirm OOMKilled via `kubectl describe pod` (Last State: Terminated,
   Reason: OOMKilled, Exit Code: 137).
2. Identify the specific job/process causing the burst (here, `ModelRefreshJob`).
3. Short-term: raise the memory limit with headroom (2Gi → 3Gi).
4. Medium-term: capture a heap dump on next OOM to find the actual spike source.
5. Consider isolating the batch job into its own pod/CronJob with a separate
   resource envelope.

## Troubleshooting
- `OOMKilling` event + `Back-off restarting failed container` + exit `137` →
  memory limit exceeded; confirm the exact job before resizing.
- Only `CrashLoopBackOff` without an `OOMKilling` event → different restart
  cause (e.g. liveness failure); do not assume OOM.