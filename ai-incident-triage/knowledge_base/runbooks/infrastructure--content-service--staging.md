---
title: High Memory Usage on content-service
service: content-service
severity_applicable: [P3]
tags: ['content-service']
version: 1
last_reviewed: 2026-09-03
owning_team: auto-generated
---

# High Memory Usage on content-service

## Symptoms
- Container memory usage is approximately 1.07 GB against a 1 Gi limit, leaving ~0% headroom.
- GC thrashing is observed, with frequent and prolonged garbage collection cycles.
- The container is one allocation spike away from an OOMKill.
- This is a high-but-stable usage pattern with a real burst profile of content lookups.

## Diagnosis Steps
1. **Verify the alert:** Confirm that the "Container High Memory Usage" alert is firing and check the exact usage vs. limit in your monitoring tool (e.g., Grafana, Datadog).
2. **Inspect container metrics:** Run `kubectl top pod <pod-name> --containers` to see current memory usage and compare to the configured limit.
3. **Check JVM heap status (content-service is a Java application):** Use `kubectl exec <pod-name> -- jcmd 1 VM.native_memory summary` or attach a jconsole/jmx client to review heap and non-heap usage.
4. **Examine GC logs:** Retrieve GC logs from the container (e.g., `/var/log/gc.log`) and look for frequency, pause time, and promotion failures that indicate memory pressure.
5. **Identify memory allocation patterns:** Review recent request traffic for content lookups to determine if a burst caused the spike or if memory is leaking over time.
6. **Rule out memory leak:** Check for retained heap dumps or increasing heap usage after GC cycles.

## Resolution
1. **Increase the memory limit** for the content-service container. A common safe step is to raise the limit from 1 Gi to 1.5 Gi or 2 Gi, depending on the application's expected peak usage. Update the Kubernetes deployment manifest and apply:
   ```yaml
   resources:
     limits:
       memory: 1.5Gi
     requests:
       memory: 1Gi
   ```
2. **Tune JVM heap settings** if a heap dump analysis shows high overhead. For example, adjust `-Xmx` and `-Xms` to 1 Gi or lower to leave room for non-heap memory. Add or modify the JVM options in the container's startup command.
3. **Optimize memory usage in the application** by reviewing content caching strategies, reducing cache TTL, or implementing a more efficient data structure.
4. **Apply the fix** and monitor the pod for at least 15 minutes to confirm memory stabilizes with sufficient headroom (~20% or more).

## Observed Incident — 2026-09-03 — INC-MEM-4002
**Severity:** P3  
**Root Cause:** Primary cause relates to: ## Container High Memory Usage

**Alert:** Container memory usage within 5% of its limit, or headroom ≈ 0%
for more than 5 minutes  
**Severity:** High  
**Routing:** platformOnCall

**Impact:**
- Heavy G

**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.

## Observed Incident — 2026-09-03 — INC-MEM-4002

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- Container memory usage is approximately 1.07 GB against a 1 Gi limit, leaving ~0% headroom.
- GC thrashing is observed, with frequent and prolonged garbage collection cycles.
- The cont
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.
