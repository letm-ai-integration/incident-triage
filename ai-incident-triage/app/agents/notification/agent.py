"""
Notification agent: composes and sends an email summarizing a resolved
incident's RCA report to the current on-call/support developer.

Recipient resolution is a deterministic mock lookup (``tools/mock/oncall.py``),
not an LLM decision; the LLM only drafts the email text from the report's actual
fields; delivery happens via the thin Resend adapter (``tools/adapters``).
"""
from __future__ import annotations

import logging

from dataclasses import dataclass

from app.agents.notification.parser import (
    NotificationEmail,
    parse_notification_response,
)
from app.agents.notification.prompt import SYSTEM_PROMPT, build_user_prompt
from app.domain.models.report import IncidentReport
from app.guardrails.safety_guard import check_content_safety
from app.guardrails.sanitize import sanitize_html_email_body
from app.llm.client import create_structured_agent
from app.tools.adapters.resend_email import EmailSendError, send_email
from app.tools.mock.oncall import get_current_oncall

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationResult:
    success: bool
    recipient: str | None = None
    message_id: str | None = None
    error: str | None = None


def _draft_email_llm(rca_report: IncidentReport, contact, model: str | None) -> NotificationEmail:
    """Draft the notification email via the LLM structured agent."""
    agent = create_structured_agent(
        system_prompt=SYSTEM_PROMPT,
        output_schema=NotificationEmail,
        model=model,
    )
    response = agent.invoke(
        {
            "messages": [
                {"role": "user", "content": build_user_prompt(rca_report, contact)}
            ]
        }
    )
    return parse_notification_response(response)


def _draft_email_template(rca_report: IncidentReport) -> NotificationEmail:
    """Deterministic fallback draft built from the report's own fields."""
    subject = (
        f"[{rca_report.classification.priority.value}] "
        f"{rca_report.incident_id} - RCA report"
    )
    body = (
        f"<h2>Incident {rca_report.incident_id} - RCA Report</h2>"
        f"<p><b>Type:</b> {rca_report.classification.incident_type.value}</p>"
        f"<p><b>Affected services:</b> "
        f"{', '.join(rca_report.classification.affected_services) or 'n/a'}</p>"
        f"<p><b>Root cause:</b> {rca_report.root_cause.primary_cause.description}</p>"
        f"<p><b>Recommended actions:</b></p>"
        f"<ul>"
        + "".join(f"<li>{action}</li>" for action in rca_report.recommended_actions)
        + "</ul>"
    )
    return NotificationEmail(subject=subject, body=body)


def run_notification_agent(
    rca_report: IncidentReport, model: str | None = None
) -> NotificationResult:
    """Compose and send the notification email for ``rca_report``.

    Failures are returned as ``NotificationResult(success=False, error=...)``
    rather than raised -- missing on-call data, an LLM/parse error, or a failed
    send all become an error result, never an uncaught exception. An LLM
    drafting failure falls back to a deterministic template so delivery still
    happens; only a send failure fails the notification.
    """
    try:
        contact = get_current_oncall()
        logger.info("[notification.agent] on-call recipient=%s (%s)", contact.email, contact.name)
    except Exception as exc:  # noqa: BLE001
        logger.error("[notification.agent] on-call lookup failed: %s", exc)
        return NotificationResult(success=False, error=str(exc))

    try:
        email = _draft_email_llm(rca_report, contact, model)
        logger.info("[notification.agent] email drafted via LLM subject=%r", email.subject)
    except Exception as exc:  # noqa: BLE001 -- LLM unavailable/failure: use template
        logger.warning(
            "[notification.agent] LLM drafting failed (%s: %s); "
            "using deterministic template fallback",
            type(exc).__name__,
            exc,
        )
        email = _draft_email_template(rca_report)
        logger.info("[notification.agent] email drafted via template subject=%r", email.subject)

    sanitized_body = sanitize_html_email_body(email.body)
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
    email = NotificationEmail(subject=email.subject, body=sanitized_body)

    try:
        message_id = send_email(to=contact.email, subject=email.subject, html_body=email.body)
    except EmailSendError as exc:
        logger.error("[notification.agent] delivery failed: %s", exc)
        return NotificationResult(success=False, error=str(exc))

    return NotificationResult(success=True, recipient=contact.email, message_id=message_id)