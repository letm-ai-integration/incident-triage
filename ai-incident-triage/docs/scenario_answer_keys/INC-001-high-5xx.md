# INC-001: High API 5xx Error Rate — Answer Key

**Actual root cause:** Capacity collapse — an HPA misconfiguration shipped
alongside the v2.4.1 release scaled checkout-service from 6 to 2 replicas at
10:04 (`minReplicas=2`); remaining pods saturated CPU under morning traffic,
inflight requests timed out against inventory-service, and the executor began
shedding load -> 5xx. The release itself was not buggy.

**Correct investigation trail:**
1. App logs (logs_traces, trace family `a11ce5ed*`): slow downstream calls ->
   retry storm -> `RejectedExecutionException` / load-shedding warnings from
   10:07 onward — symptoms only, no new exception type.
2. Metrics: `error_rate_pct` ramps 1.2 -> 38 while `cpu_pct` on surviving pods
   climbs to 97% and `replica_count` drops 6 -> 2 at 10:04.
3. k8s_logs: HPA scale-down event at 10:04 naming `minReplicas=2`; liveness
   probe failures/restarts during peak are secondary fallout.
4. deployment_events: v2.4.1 completed 10:03 (temporal correlation), rollback
   to v2.4.0 completed 10:25 with immediate recovery.

**Contributing factors:** retry amplification increased effective load.
**Primary vs. secondary:** metrics + the HPA event are the evidence; app logs
are the symptom surface; the deployment is a deliberate red herring toward a
code-regression conclusion (no new error class exists to support it).
**Red herrings present:** transient 502 on `/api/v1/cart` self-resolving in
~2s; notification-service SMTP slowness; orders-07 benign rolling restart.
**Expected resolution:** roll back / restore replicas (HPA fix) as mitigation;
correct the autoscaler floor as follow-up.
