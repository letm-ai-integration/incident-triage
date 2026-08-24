# INC-005: Deployment Regression — Answer Key

**Actual root cause:** Bad release v3.1.0 on inventory-service — the rollout
shipped a serializer change (`StockCacheMapper`) that raises
ClassCastException on legacy V1 stock-cache payloads. Errors start at 10:47,
exactly one minute after rollout completion (10:46); rollback to v3.0.9 at
10:53–10:55 restores service.

**Correct investigation trail:**
1. deployment_events: v3.1.0 completed 10:46; `rolled_back` to v3.0.9 logged
   at 10:53 initiated by m.okafor.
2. App logs (logs_traces, trace family `f00dface*`): a NEW error class
   (ClassCastException in StockCacheMapper) appears at 10:47 and vanishes
   after rollback — presence of a brand-new exception type is the regression
   fingerprint.
3. Metrics: `error_rate_pct` jumps 0.4 -> 22 within minutes of rollout and
   recovers post-rollback.
4. k8s_logs: readiness-probe failures (no restarts) are secondary fallout.

**Contributing factors:** none — deterministic failure on legacy payloads.
**Primary vs. secondary:** deployment timing + new-error-class correlation is
the evidence; probe failures are secondary. frontend-web's v6.7.2 deploy at
10:40 is the decoy release.
**Red herrings present:** unrelated frontend-web deploy completion at 10:40;
auth cert-rotation warning; a canary request succeeding at 10:48 (mixed
results).
**Expected resolution:** roll back to v3.0.9 (mirrors runbook "High API
Failures" step: deploy-correlated failure -> immediate rollback), then fix
the mapper for V1 payloads before re-release.
