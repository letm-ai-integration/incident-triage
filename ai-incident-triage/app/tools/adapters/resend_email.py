"""
Resend email adapter. Thin wrapper -- no business logic, no recipient
resolution. Callers pass a fully-formed message; this module only sends it.
"""
from __future__ import annotations

import logging

import resend

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    pass


def send_email(to: str, subject: str, html_body: str) -> str:
    """Sends an email via Resend. Returns the Resend message id on success."""
    settings = get_settings()
    if not settings.resend_api_key:
        raise EmailSendError("RESEND_API_KEY is not configured")

    resend.api_key = settings.resend_api_key

    logger.info(
        "[resend.adapter] sending email to=%s from=%s subject=%r",
        to,
        f"{settings.resend_from_name} <{settings.resend_from_email}>",
        subject,
    )
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
        logger.error("[resend.adapter] send failed: %s", e)
        raise EmailSendError(f"Failed to send email via Resend: {e}") from e

    logger.info("[resend.adapter] sent successfully message_id=%s", response["id"])
    return response["id"]