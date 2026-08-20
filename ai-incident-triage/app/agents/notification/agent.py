"""
Notification agent: composes and sends an email summarizing a resolved
incident's RCA report to the current on-call/support developer.

Recipient resolution is a deterministic mock lookup (``tools/mock/oncall.py``),
not an LLM decision; the LLM only drafts the email text from the report's actual
fields; delivery happens via the thin Resend adapter (``tools/adapters``).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.agents.notification.parser import (
    NotificationEmail,
    parse_notification_response,
)
from app.agents.notification.prompt import SYSTEM_PROMPT, build_user_prompt
from app.domain.models.report import IncidentReport
from app.llm.client import create_structured_agent
from app.tools.adapters.resend_email import EmailSendError, send_email
from app.tools.mock.oncall import get_current_oncall


@dataclass(frozen=True)
class NotificationResult:
    success: bool
    recipient: str | None = None
    message_id: str | None = None
    error: str | None = None


def run_notification_agent(
    rca_report: IncidentReport, model: str | None = None
) -> NotificationResult:
    """Compose and send the notification email for ``rca_report``.

    Failures are returned as ``NotificationResult(success=False, error=...)``
    rather than raised -- missing on-call data, an LLM/parse error, or a failed
    send all become an error result, never an uncaught exception.
    """
    try:
        contact = get_current_oncall()
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
        email = parse_notification_response(response)
        message_id = send_email(to=contact.email, subject=email.subject, html_body=email.body)
    except EmailSendError as exc:
        return NotificationResult(success=False, error=str(exc))
    except Exception as exc:  # noqa: BLE001 -- any failure becomes an error result
        return NotificationResult(success=False, error=str(exc))

    return NotificationResult(success=True, recipient=contact.email, message_id=message_id)