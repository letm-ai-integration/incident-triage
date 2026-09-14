"""
Notification agent: composes and sends an email summarizing an incident's RCA
report to the current on-call/support developer.

ONE rendering function: the email body is ALWAYS the fixed HTML template
(``render_html_email_report``) rendered from the validated report -- the LLM
drafts only the subject line, with the honest deterministic subject as
fallback. Recipient resolution is a deterministic mock lookup
(``tools/mock/oncall.py``), not an LLM decision; delivery happens via the thin
Resend adapter (``tools/adapters``).
"""
from __future__ import annotations

import html
import logging
from dataclasses import dataclass

from app.agents.notification.parser import (
    NotificationEmail,
    NotificationSubject,
    parse_notification_response,
)
from app.agents.notification.prompt import SYSTEM_PROMPT, build_user_prompt
from app.domain.models.incident import Incident
from app.domain.models.report import IncidentReport
from app.guardrails.pii_guard import redact_pii
from app.guardrails.safety_guard import check_content_safety
from app.llm.client import create_structured_agent
from app.logging_utils import agent_entry, agent_error, agent_exit, agent_output
from app.tools.adapters.resend_email import EmailSendError, send_email
from app.tools.mock.oncall import get_current_oncall

logger = logging.getLogger(__name__)

# Pipeline honesty gates (mirrors the subject wording rules in the prompt):
# unless the report verifies resolution, a subject claiming a fix happened is
# rejected and replaced by the deterministic honest subject.
_SUBJECT_BANNED_WORDS = (
    "resolved", "fixed", "remediated", "restarted", "scaled", "increased", "applied",
)


def _honest_subject(subject: str, rca_report: IncidentReport) -> str:
    """Return ``subject`` if it passes the pipeline's wording gates, else "".

    Only gates when remediation is NOT applied-and-verified: an LLM subject
    that claims resolution for a pending incident is replaced by the
    deterministic honest subject ("(remediation pending)").
    """
    if rca_report.verification.is_resolved:
        return subject
    lowered = subject.lower()
    for word in _SUBJECT_BANNED_WORDS:
        if word in lowered:
            logger.warning(
                "[notification.agent] LLM subject rejected by honesty gate "
                "(contains %r while remediation is pending): %r",
                word,
                subject,
            )
            return ""
    return subject


@dataclass(frozen=True)
class NotificationResult:
    success: bool
    recipient: str | None = None
    message_id: str | None = None
    error: str | None = None


def _draft_subject_llm(rca_report: IncidentReport, contact, model: str | None) -> str:
    """Draft only the email SUBJECT via the LLM structured agent.

    The body is never LLM-drafted (see module docstring): the old schema let
    the LLM return plain text as the "html" body, which Resend delivered as a
    plain-looking email instead of the styled template.
    """
    agent = create_structured_agent(
        system_prompt=SYSTEM_PROMPT,
        output_schema=NotificationSubject,
        model=model,
    )
    response = agent.invoke(
        {
            "messages": [
                {"role": "user", "content": build_user_prompt(rca_report, contact)}
            ]
        }
    )
    return parse_notification_response(response).subject


def _draft_email_template(rca_report: IncidentReport, run_id: str | None = None) -> NotificationEmail:
    """Deterministic fallback draft built from the report's own fields.

    Renders the fixed Phase 5 canonical template (all sections, in order)
    from already-validated report fields only via the single reusable HTML template
    (``app/prompts/templates/incident_report_email.html``); environment and priority
    come from the incident's own values, never invented. This pipeline only
    investigates and recommends, so the email never claims a fix was applied
    unless the report's verification says recovery was validated.
    """
    from app.services.email_report_renderer import render_html_email_report

    subject = (
        f"[{rca_report.classification.priority.value}] "
        f"{rca_report.incident_id} - RCA report"
    )
    if not rca_report.verification.is_resolved:
        subject += " (remediation pending)"

    body = render_html_email_report(rca_report, run_id=run_id)
    return NotificationEmail(subject=subject, body=body)



def run_notification_agent(
    rca_report: IncidentReport, model: str | None = None, run_id: str | None = None
) -> NotificationResult:
    """Compose and send the notification email for ``rca_report``.

    ONE rendering function: the body is ALWAYS the fixed HTML template
    (``render_html_email_report``) rendered from the validated report -- the
    LLM only drafts the subject line (deterministic subject on any LLM
    failure). Failures are returned as ``NotificationResult(success=False,
    error=...)`` rather than raised; only a failed send fails the
    notification.
    """
    agent_entry("NotificationAgent", f"incident={rca_report.incident_id}")
    try:
        contact = get_current_oncall()
        logger.info("[notification.agent] on-call recipient=%s (%s)", contact.email, contact.name)
    except Exception as exc:  # noqa: BLE001
        logger.error("[notification.agent] on-call lookup failed: %s", exc)
        agent_error("NotificationAgent", exc, "on-call lookup failed")
        agent_exit("NotificationAgent")
        return NotificationResult(success=False, error=str(exc))

    # Subject: LLM-drafted, with the honest deterministic subject as fallback.
    try:
        subject = _draft_subject_llm(rca_report, contact, model)
        logger.info("[notification.agent] subject drafted via LLM subject=%r", subject)
    except Exception as exc:  # noqa: BLE001 -- LLM unavailable/failure: template subject
        logger.warning(
            "[notification.agent] LLM subject drafting failed (%s: %s); "
            "using deterministic subject",
            type(exc).__name__,
            exc,
        )
        agent_error("NotificationAgent", exc, "LLM subject drafting failed, using template")
        subject = None

    # Body: ALWAYS the single fixed HTML template rendered from validated
    # report fields -- never LLM output, never plain text.
    email = _draft_email_template(rca_report, run_id=run_id)
    logger.info("[notification.agent] body rendered via fixed HTML template subject=%r", email.subject)

    subject = _honest_subject(subject or email.subject, rca_report) or email.subject
    # LLM subject is untrusted free-form: collapse whitespace/newlines to one
    # line before it becomes a mail header value.
    subject = " ".join(subject.split())

    # The template body is trusted static HTML filled with autoescaped,
    # validated report values -- it must keep its inline CSS (table layout,
    # badges) for Outlook-compatible delivery, so the LLM allow-list sanitizer
    # is not applied here (it would strip `style=` attributes and break the
    # styled layout). PII redaction of incident-derived text (description,
    # logs, findings) happens field-by-field in
    # ``email_report_renderer._build_context`` before rendering -- not here
    # on the whole rendered HTML -- so it never touches generated metadata
    # like the run id or timestamp (e.g. a run id ending in "...20260912"
    # otherwise reads as a phone-number-shaped digit run to the PII regex).
    sanitized_body = email.body
    subject = redact_pii(subject)

    safety_result = check_content_safety("notification", sanitized_body)
    if not safety_result.passed:
        logger.error(
            "[notification.agent] content-safety guardrail blocked email incident=%s findings=%s",
            rca_report.incident_id,
            safety_result.findings,
        )
        return NotificationResult(
            success=False,
            error=f"blocked by content-safety guardrail: {safety_result.findings}",
        )
    email = NotificationEmail(subject=subject, body=sanitized_body)

    try:
        message_id = send_email(to=contact.email, subject=email.subject, html_body=email.body)
    except EmailSendError as exc:
        logger.error("[notification.agent] delivery failed: %s", exc)
        agent_error("NotificationAgent", exc, "email delivery failed")
        agent_exit("NotificationAgent")
        return NotificationResult(success=False, error=str(exc))

    agent_output("NotificationAgent", f"delivered to={contact.email} message_id={message_id}")
    agent_exit("NotificationAgent")
    return NotificationResult(success=True, recipient=contact.email, message_id=message_id)


def notify_quarantine(incident: Incident, guardrail_findings: list[dict]) -> NotificationResult:
    """Send a security-alert email for an incident quarantined at ingestion
    (see app/graph/nodes/ingestion.py) -- no RCA report exists yet, so this
    bypasses the RCA email template entirely and never includes the
    incident's raw description/logs: that untrusted content is exactly what
    is being kept away from automated (and now email) rendering, a human
    reviews it directly instead.
    """
    agent_entry("NotificationAgent", f"incident={incident.incident_id} quarantined=True")
    try:
        contact = get_current_oncall()
        logger.info("[notification.agent] on-call recipient=%s (%s)", contact.email, contact.name)
    except Exception as exc:  # noqa: BLE001
        logger.error("[notification.agent] on-call lookup failed: %s", exc)
        agent_error("NotificationAgent", exc, "on-call lookup failed")
        agent_exit("NotificationAgent")
        return NotificationResult(success=False, error=str(exc))

    subject = redact_pii(f"[SECURITY] Incident {incident.incident_id} quarantined at ingestion")
    title = html.escape(redact_pii(incident.title))
    checks = "".join(
        f"<li>{html.escape(item.get('check', ''))}: {html.escape('; '.join(item.get('findings', [])))}</li>"
        for item in guardrail_findings
    ) or "<li>(no findings recorded)</li>"
    body = (
        "<h2>Incident quarantined before automated triage</h2>"
        f"<p>Incident <b>{html.escape(incident.incident_id)}</b> "
        f"(service: {html.escape(incident.service)}, environment: {html.escape(incident.environment.value)}) "
        "was flagged by an input guardrail at ingestion and was <b>not</b> passed to the "
        "classification/investigation/RCA pipeline.</p>"
        f"<p><b>Title:</b> {title}</p>"
        "<p><b>Guardrail findings:</b></p>"
        f"<ul>{checks}</ul>"
        "<p>Please review the raw incident content manually before deciding whether to "
        "re-submit it for automated triage.</p>"
    )

    try:
        message_id = send_email(to=contact.email, subject=subject, html_body=body)
    except EmailSendError as exc:
        logger.error("[notification.agent] quarantine alert delivery failed: %s", exc)
        agent_error("NotificationAgent", exc, "quarantine alert delivery failed")
        agent_exit("NotificationAgent")
        return NotificationResult(success=False, error=str(exc))

    agent_output("NotificationAgent", f"quarantine alert delivered to={contact.email} message_id={message_id}")
    agent_exit("NotificationAgent")
    return NotificationResult(success=True, recipient=contact.email, message_id=message_id)