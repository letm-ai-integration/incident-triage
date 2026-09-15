# Guardrail-Quarantine Notification: Dedicated HTML Template (Scoped Change Only)

## Critical scope boundary — read this before touching anything

This task affects **one specific notification path only**: the message sent when an input guardrail quarantines an incident *before* it ever reaches classification/investigation/RCA. It does **not** affect the main Incident Summary HTML template or renderer built in earlier work for normal investigated incidents.

- Do **not** modify the existing Incident Summary template, its renderer, or any code shared with the normal investigation-complete notification path, unless the *only* way to route quarantine notifications correctly is through a shared dispatch point that just needs a conditional branch added (see Phase 1 — confirm this before assuming it).
- Do **not** touch any other incident's data, any other notification, or any other part of the pipeline (graph, agents, UI) while doing this.
- The three files below are the target test fixtures for this change — do not modify any other file in `data/incidents/` as part of this task:
  - `ai-incident-triage/data/incidents/pii-leaked-contact-info.json`
  - `ai-incident-triage/data/incidents/prompt-injection-attempt.json`
  - `ai-incident-triage/data/incidents/unsafe-content-in-logs.json`

This must work for **any** incident that trips a guardrail, not just these three — but these three are what you test against.

---

## Why this needs its own template, not the existing one

A guardrail-quarantined incident is a fundamentally different message from a completed investigation: nothing was classified, investigated, or analyzed — the pipeline never ran. Forcing this into the existing Incident Summary template (which has sections like Root Cause Analysis, Recommended Remediation, Investigation Status) would either leave those sections awkwardly empty/fake or require inventing content that doesn't exist. This needs a distinct, purpose-built template that honestly represents "this was stopped before triage" — visually distinct enough that a recipient immediately knows this is a different kind of alert than a normal incident report.

---

## PHASE 1 — Find the existing quarantine-notification code path

Before writing any template, locate exactly where the plain-text quarantine message (the one you already received, starting "Incident quarantined before automated triage...") is currently generated and sent. Trace:
- Which node/service intercepts an incident after a guardrail match (this is likely in `ingestion` or a dedicated `guardrail`/`safety` check that runs before the graph's main path) and short-circuits it away from classification/investigation.
- Where the actual notification text is composed and handed off to the send mechanism.
- Whether this reuses the same "send notification" function as the main investigation-complete path (likely yes — the same underlying email-sending code, just with different content), or whether it's fully separate. This determines whether Phase 2's new template needs its own render function that plugs into the *existing* send mechanism (most likely and least risky), or something more separate.

Report back what you find before proceeding to Phase 2 — confirm the exact function/file you intend to add the new template into, so we can agree the scope stays narrow.

---

## PHASE 2 — Build the dedicated Guardrail Quarantine HTML template

Use the same technical constraints as the earlier Incident Summary template: **table-based HTML with inline CSS** (not flexbox/grid) for email-client compatibility, HTML-escape all incident-derived text before insertion, and handle missing fields with explicit fallback text rather than blank space.

### Structure

**Header band** — visually distinct from the normal report's coral "Incident Summary" banner, since this must read as a different category of alert at a glance. Use a warning/alert color scheme (e.g. a dark amber or red band, not the standard coral):
- Large label: `QUARANTINED — NOT SUBMITTED FOR AUTOMATED TRIAGE`
- Incident ID
- Service and Environment, shown together (e.g. `community-uploads · PRODUCTION`)

**Body sections, in this order:**

1. **What happened** — one short paragraph, e.g.: "This incident was flagged by an input guardrail at ingestion and was not passed to the classification, investigation, or RCA pipeline." (Compose this from the actual guardrail-stage data, don't hardcode the wording if the reason/stage can vary.)
2. **Incident Title** — the incident's reported title, rendered clearly (e.g. as a subheading), HTML-escaped.
3. **Guardrail Findings** — a table with columns `Check`, `Category`, `Detail`. Populate one row per guardrail finding (e.g. `check_content_safety` / `safety` / `matched keyword 'how to make explosives'`). If there are multiple findings, show all of them as separate rows, not concatenated into one cell. If no structured findings are available (only a raw message), fall back to a single row showing the raw guardrail message rather than omitting the section.
4. **Required Action** — a visually distinct callout box (bordered, tinted background matching the header's warning color, not the same styling as the normal report's "no runbook" callout so the two alert types don't look identical): "Please review the raw incident content manually before deciding whether to re-submit it for automated triage." Keep this exact wording unless the underlying guardrail-stage data suggests a different action is more appropriate for a given guardrail type — if so, make this line data-driven rather than a hardcoded string, falling back to the wording above when no more specific guidance exists.

**Footer band** — same style as the main template's footer: small muted text with the run/incident ID and a one-line note that this is an automated message.

### Edge-case handling
- Missing service/environment → render `Not specified`, same convention as the main template — never blank.
- Missing/empty guardrail findings list → fall back to the raw quarantine message as described above; never render an empty table with no rows and no explanation.
- Multiple guardrail checks triggering at once → all must appear as separate rows, not merged or only the first one shown.
- Apply the same HTML-escaping requirement as the main template to every piece of incident-derived text (title, guardrail detail strings) — this is especially important here since quarantined content is, by definition, flagged as potentially unsafe/malicious input, so it must never be trusted to be safe to insert into HTML unescaped.

---

## PHASE 3 — Wire it in, scoped only to the guardrail path

Update only the specific function/branch identified in Phase 1 so that when an incident is quarantined by a guardrail, this new template is used to render the notification — and confirm the normal investigation-complete path is completely unaffected (it must still use the original Incident Summary template exactly as before, with zero code shared in a way that could let a future change to one accidentally affect the other, beyond the common low-level "send an email" utility if that's genuinely shared infrastructure).

---

## PHASE 4 — Verify against the three test incidents, and confirm nothing else changed

1. Run each of the three fixture incidents (`pii-leaked-contact-info.json`, `prompt-injection-attempt.json`, `unsafe-content-in-logs.json`) through the pipeline and confirm each produces a properly rendered HTML quarantine notification — not plain text — with the correct incident-specific guardrail findings shown for each (they should NOT all show the same "explosives" finding from the example above — each of these three represents a different guardrail category: PII leakage, prompt injection, and unsafe content in logs respectively, so confirm the findings table reflects the actual check/category/detail relevant to each one).
2. Run at least one normal, non-quarantined incident (e.g. `INC-006` or one of the earlier mock incidents) through the pipeline afterward and confirm its notification is completely unchanged — still the original Incident Summary HTML template, unaffected by this work.
3. Confirm no other file outside of the quarantine-notification code path and its new template was modified.

## Verification checklist
- [ ] The quarantine notification is now HTML, not plain text, for all three test incidents.
- [ ] Each of the three test incidents shows its own correct, distinct guardrail finding(s) — not a copy-pasted example.
- [ ] The quarantine template is visually distinct from the normal Incident Summary template (different header color/labeling) so the two are never confused at a glance.
- [ ] All fields degrade gracefully per the edge cases above — no blank sections, no raw `None`/`null` in output.
- [ ] A normal, already-working incident's notification is verified unchanged after this work.
- [ ] No file outside the guardrail-notification path and its new template was touched.

Report back with the rendered HTML output for all three test incidents so I can review before we call this done.
