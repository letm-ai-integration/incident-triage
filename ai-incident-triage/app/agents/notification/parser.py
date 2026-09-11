"""Extracts the typed email content from a structured-agent invocation."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class NotificationSubject(BaseModel):
    """LLM-drafted subject line only.

    The body is NEVER drafted by the LLM -- it always comes from the single
    fixed HTML template renderer (``render_html_email_report``), so the styled
    template is delivered on every send. The old subject+body schema let the
    LLM return plain text as the "html" body, which Resend delivered verbatim
    as a plain-looking email.
    """

    subject: str


class NotificationEmail(BaseModel):
    """Fully-formed notification email (template-rendered body included)."""

    subject: str
    body: str


def parse_notification_response(agent_response: dict[str, Any]) -> NotificationSubject:
    structured = agent_response.get("structured_response")
    if not isinstance(structured, NotificationSubject):
        raise TypeError(
            "Notification agent did not return a structured_response of type "
            f"NotificationSubject (got {type(structured)!r})."
        )
    return structured