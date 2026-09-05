---
title: DNS resolution failures causing intermittent timeouts on cart-service
service: cart-service
severity_applicable: [P2]
tags: ['cart-service']
version: 1
last_reviewed: 2026-09-02
owning_team: auto-generated
---

# DNS Resolution Failures Causing Intermittent Timeouts on cart-service

## Symptoms
- Cart-service intermittently fails to resolve `cart-cache.redis.svc.cluster.local` via CoreDNS.
- Cache read/write operations time out despite the redis cache being healthy.
- No CPU or memory pressure on cart-service pods.
- Alert triggers on rising DNS SERVFAIL/NXDOMAIN/timeout rate from the service resolver.

## Diagnosis Steps
1. **Check DNS resolution from within the affected pod**:  
   `kubectl exec <cart-service-pod> -- nslookup cart-cache.redis.svc.cluster.local`  
   Look for SERVFAIL, NXDOMAIN, or timeout responses.
2. **Verify CoreDNS pod health**:  
   `kubectl get pods -n kube-system -l k8s-app=kube-dns`  
   Ensure all CoreDNS pods are running and ready.
3. **Inspect CoreDNS logs**:  
   `kubectl logs -n kube-system -l k8s-app=kube-dns --tail=100`  
   Look for upstream resolver errors or timeouts.
4. **Check CoreDNS ConfigMap for misconfiguration**:  
   `kubectl describe configmap coredns -n kube-system`  
   Verify forwarders, rewrites, and plugin settings.
5. **Test external DNS resolution** to rule out upstream resolver issues:  
   `kubectl exec <cart-service-pod> -- nslookup google.com`
6. **Look for network policy or CNI issues** that may prevent CoreDNS from reaching upstream resolvers or the kube-dns service.

## Resolution
1. **Restart CoreDNS pods** to clear transient state:  
   `kubectl rollout restart -n kube-system deployment/coredns`
2. **If restart does not resolve**, verify and correct the CoreDNS ConfigMap. Common fixes include:
   - Ensuring `forward . /etc/resolv.conf` uses valid upstream resolvers.
   - Verifying the `kubernetes` plugin is correctly configured for the cluster domain.
   - Removing any malformed rewrite or plugin entries.
3. **Ensure network connectivity** between CoreDNS pods and the kube-dns service endpoint:
   - Check `kubectl get svc kube-dns -n kube-system` for a valid ClusterIP.
   - Validate no blocking network policies exist in the `kube-system` namespace.
4. **After fix**, confirm recovery by repeatedly resolving the target hostname:  
   `for i in {1..10}; do kubectl exec <cart-service-pod> -- nslookup cart-cache.redis.svc.cluster.local; sleep 1; done`  
   Expect all queries to return a valid A record without errors.

## Observed Incident — 2026-09-02 — INC-NET-4005
**Severity:** P2
**Root Cause:** Primary cause relates to DNS Resolution Failures

**Alert:** Rising DNS SERVFAIL/NXDOMAIN/timeout rate from a service's resolver, or intermittent connection timeouts to in-cluster hostnames
**Severity:** High
**Routing:** 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.

## Observed Incident — 2026-09-02 — INC-NET-4005

**Severity:** P2
**Root Cause:** Primary cause relates to: ## Symptoms

- Cart-service intermittently fails to resolve `cart-cache.redis.svc.cluster.local` via CoreDNS.
- Cache read/write operations time out despite the redis cache being healthy.
- No CPU or 
**Resolution Evidence:** Diagnosis verified: root-cause confidence 0.95 meets the threshold and a runbook-recommended fix exists. No fix has been applied by this system; remediation is pending on-call action.
