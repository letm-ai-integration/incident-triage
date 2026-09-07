# TLS Certificate Expiration Remediation

## Overview
Outbound TLS connections to an upstream provider fail during handshake because
the presented certificate has expired. Internal service health stays UP — the
failure is scoped to the specific TLS endpoint. Expiry and handshake failures
are directly observed; the certificate is not considered replaced until
execution evidence exists.

## Solution
1. Confirm certificate chain and expiry on the affected endpoint.
2. Renew/replace the expired certificate via the approved cert-management
   process.
3. Reload/redeploy the affected TLS client config if required.
4. Validate successful handshakes and delivery after the change.

## Troubleshooting
- `TLS handshake failed` + `certificate has expired` + internal health UP →
   renew the affected endpoint cert via this runbook.
- Handshake failures without an expiry in the reason → key usage/hostname
  mismatch; verify the chain before renewal.