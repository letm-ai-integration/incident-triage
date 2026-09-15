"""Render the guardrail-quarantine notification HTML.

Dedicated counterpart to ``app/services/email_report_renderer.py``: quarantined
incidents never reached classification/investigation/RCA, so they must NOT use
the Incident Summary template (its Root Cause / Remediation / Investigation
Status sections would be empty or invented). This module renders
``app/prompts/templates/guardrail_quarantine_email.html`` instead -- a
purpose-built, warning-styled alert that honestly represents "this was stopped
before triage".

Kept fully independent of the Incident Summary renderer: its own Jinja2
environment, its own template, no shared helpers -- so a future change to one
can never silently affect the other. Only the low-level ``send_email`` adapter
(``app/tools/adapters/resend_email.py``) is shared, which is genuine
infrastructure.

Security: the Jinja2 environment renders with ``autoescape=True``, so every
incident-derived value (title, guardrail detail strings) is HTML-escaped before
it reaches the template. That matters most here: quarantined content is by
definition flagged as potentially unsafe/malicious input and must never be
trusted as safe to insert into HTML. PII is additionally redacted from
incident-derived free text, mirroring the Incident Summary renderer.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2

from app.domain.models.incident import Incident
from app.guardrails.pii_guard import redact_pii

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "prompts" / "templates"
_TEMPLATE_NAME = "guardrail_quarantine_email.html"

_JP = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

# Fixed across every quarantined incident -- the identity of the alert type must
# never vary incident-to-incident (only the data below it does).
QUARANTINE_ALERT_LABEL = "QUARANTINED — NOT SUBMITTED FOR AUTOMATED TRIAGE"

_NOT_SPECIFIED = "Not specified"

_RAW_FALLBACK = (
    "This incident was flagged by an input guardrail at ingestion and was not "
    "passed to the classification, investigation, or RCA pipeline."
)

# Fallback mapping from the ingestion guardrail check function name to the
# guardrail category. The detail strings are normally prefixed with the
# category (e.g. "pii:email detected"), which is preferred when present.
_CHECK_CATEGORIES = {
    "check_pii": "pii",
    "check_prompt_injection": "prompt_injection",
    "check_content_safety": "safety",
    "check_domain_consistency": "domain",
}
_KNOWN_CATEGORIES = {"pii", "prompt_injection", "safety", "domain"}

_DEFAULT_REQUIRED_ACTION = (
    "Please review the raw incident content manually before deciding whether to "
    "re-submit it for automated triage."
)

# More specific guidance per guardrail category; when nothing matches, the exact
# default wording above is used.
_REQUIRED_ACTION_BY_CATEGORY = {
    "prompt_injection": (
        "Do not feed the submitted content to any automated or LLM-based tooling. "
        "Preserve the raw payload for security review, and re-submit a reviewed, "
        "sanitized version only if the incident is genuine."
    ),
    "pii": (
        "Treat the leaked personal data as a privacy incident: restrict access to "
        "the raw content to the incident responders, notify the data-protection "
        "owner, and scrub the data before re-submitting it for automated triage."
    ),
    "safety": (
        "Route the flagged content to the trust-and-safety/security review process, "
        "and do not re-submit the raw content for automated triage until it has "
        "been cleared."
    ),
}

# Stable order so a multi-category incident renders deterministically.
_CATEGORY_ORDER = ("prompt_injection", "safety", "pii", "domain")


def _category(finding: dict[str, Any]) -> str:
    """Category for one accumulated guardrail finding.

    Preferred source is the ``<category>:`` prefix the guardrail checks put on
    every detail string (e.g. ``pii:email detected``); the check-function name
    is the fallback.
    """
    details = finding.get("findings") or []
    if isinstance(details, str):
        details = [details]
    for detail in details:
        if isinstance(detail, str) and ":" in detail:
            prefix = detail.split(":", 1)[0].strip().lower()
            if prefix in _KNOWN_CATEGORIES:
                return prefix
    check = str(finding.get("check") or "").strip()
    return _CHECK_CATEGORIES.get(check, "unknown")


def _finding_rows(guardrail_findings: list[dict[str, Any]]) -> list[dict[str, str]]:
    """One row per guardrail finding detail string (never merged into one cell)."""
    rows: list[dict[str, str]] = []
    for finding in guardrail_findings:
        if not isinstance(finding, dict):
            continue
        check = str(finding.get("check") or "unknown")
        category = _category(finding)
        details = finding.get("findings") or []
        if isinstance(details, str):
            details = [details]
        details = [d for d in details if isinstance(d, str) and d.strip()]
        if not details:
            details = [_RAW_FALLBACK]
        for detail in details:
            rows.append(
                {
                    "check": check,
                    "category": category,
                    "detail": redact_pii(detail),
                }
            )
    return rows


def _service_environment(incident: Incident) -> str:
    """``<service> · <ENVIRONMENT>``, never blank -- ``Not specified`` per field."""
    service = (incident.service or "").strip()
    if not service or service.lower() == "unknown":
        service = _NOT_SPECIFIED
    environment = getattr(incident.environment, "value", None)
    environment = str(environment or "").strip()
    if not environment:
        environment = _NOT_SPECIFIED
    return f"{service} · {environment}"


def _what_happened(findings: list[dict[str, Any]], rows: list[dict[str, str]]) -> str:
    """Compose the summary from the actual guardrail-stage data.

    The stage/node and the triggering categories come from the recorded
    findings rather than being hardcoded, so the sentence stays accurate if the
    guardrail stage or set of checks ever changes.
    """
    if not rows:
        return _RAW_FALLBACK
    nodes = sorted(
        {
            str(finding.get("node") or "").strip()
            for finding in findings
            if isinstance(finding, dict) and str(finding.get("node") or "").strip()
        }
    )
    stage = " / ".join(nodes) if nodes else "ingestion"
    categories = ", ".join(sorted({row["category"] for row in rows}))
    return (
        f"This incident was flagged by an input guardrail at the {stage} stage "
        f"({categories}) and was not passed to the classification, investigation, "
        f"or RCA pipeline."
    )


def _required_action(rows: list[dict[str, str]]) -> str:
    """Per-category guidance when available, else the exact default wording."""
    categories = {row["category"] for row in rows}
    actions = [
        _REQUIRED_ACTION_BY_CATEGORY[category]
        for category in _CATEGORY_ORDER
        if category in categories
    ]
    if not actions:
        return _DEFAULT_REQUIRED_ACTION
    return " ".join(actions)
def render_quarantine_html_email(
    incident: Incident,
    guardrail_findings: list[dict[str, Any]] | None = None,
    run_id: str | None = None,
    raw_quarantine_message: str | None = None,
) -> str:
    """Render the quarantine alert HTML for ``incident``.

    * ``guardrail_findings`` is the accumulated ``state["guardrail_findings"]``
      list produced by ingestion; every detail string becomes its own table row.
    * When no structured findings exist, a single row showing
      ``raw_quarantine_message`` (or the honest default sentence) is rendered
      instead of an empty table.
    * ``run_id`` is rendered in the footer and resolves to ``Not recorded`` when
      absent -- never a raw ``None`` (and never invented).
    """
    findings = [f for f in (guardrail_findings or []) if isinstance(f, dict)]
    rows = _finding_rows(findings)
    if not rows:
        raw = (raw_quarantine_message or "").strip() or _RAW_FALLBACK
        rows = [
            {
                "check": "guardrail",
                "category": "quarantine",
                "detail": redact_pii(raw),
            }
        ]

    title = (incident.title or "").strip() or _NOT_SPECIFIED
    context = {
        "alert_label": QUARANTINE_ALERT_LABEL,
        "incident_id": incident.incident_id or _NOT_SPECIFIED,
        "service_environment": _service_environment(incident),
        "what_happened": _what_happened(findings, rows),
        "incident_title": redact_pii(title),
        "findings_rows": rows,
        "required_action": _required_action(rows),
        "run_id": (run_id or "").strip() or "Not recorded",
    }
    template = _JP.get_template(_TEMPLATE_NAME)
    return template.render(**context)


__all__ = ["QUARANTINE_ALERT_LABEL", "render_quarantine_html_email"]
