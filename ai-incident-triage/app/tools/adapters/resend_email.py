"""
Resend email adapter. Thin wrapper -- no business logic, no recipient
resolution. Callers pass a fully-formed message; this module only sends it.
"""
from __future__ import annotations

import resend

from app.config import get_settings


class EmailSendError(Exception):
    pass


def send_email(to: str, subject: str, html_body: str) -> str:
    """Sends an email via Resend. Returns the Resend message id on success."""
    settings = get_settings()
    if not settings.resend_api_key:
        raise EmailSendError("RESEND_API_KEY is not configured")

    resend.api_key = settings.resend_api_key

    try:
        response = resend.Emails.send(
            {
                "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                "to": [to],
                "subject": subject,
                "html": html_body,
            }
        )
    except Exception as e:
        raise EmailSendError(f"Failed to send email via Resend: {e}") from e

    return response["id"]