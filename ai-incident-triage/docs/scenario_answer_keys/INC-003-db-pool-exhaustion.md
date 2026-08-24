# INC-003: DB Connection Pool Exhaustion — Answer Key

**Actual root cause:** Connection leak in order-service — pool utilization
pinned at 100% with a climbing waiter count while request traffic stayed flat
(~180 rps) and the DB primary logged zero slow queries. Connections were
acquired but not returned, exhausting HikariPool-1.

**Correct investigation trail:**
1. db_logs: `[order-db-pool] active=50 idle=0 waiting=...` climbing 2 -> 34
   with `slow_query_log: 0 statements` every minute — rules out query
   regression AND rules out a DB-side problem.
2. Metrics: `hikari_pool_utilization_pct` flatlined at 100 while
   `requests_per_sec` stayed ~180 — rules out a traffic spike; the mismatch
   between flat demand and full pool is the leak signature.
3. App logs (logs_traces, trace family `c0ffee01*`): HikariPool acquisition
   timeouts and `SQLTransientConnectionException` stack traces — symptom only.
4. k8s_logs has NO entries for order-service in this window — the cluster is
   healthy; pod-level action would be mis-attribution.

**Contributing factors:** none material.
**Primary vs. secondary:** db pool stats + flat-traffic metrics are the
evidence; app log timeouts are the symptom.
**Red herrings present:** 4120ms query on the *analytics replica* (different
database, irrelevant to order-db-pool); notification queue flush noise;
brief benign traffic blip.
**Expected resolution:** rolling restart of order-service to reclaim leaked
connections (mirrors runbook "Database Connection Pool Exhausted"), then fix
the unclosed-connection code path.
