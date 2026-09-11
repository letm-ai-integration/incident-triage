"""
Resend email adapter. Thin wrapper -- no business logic, no recipient
resolution. Callers pass a fully-formed message; this module only sends it.
"""
from __future__ import annotations

import logging
import re

import resend

from app.config import get_settings

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[a-zA-Z][^>]*>")


class EmailSendError(Exception):
    pass


def send_email(to: str, subject: str, html_body: str) -> str:
    """Sends an email via Resend. Returns the Resend message id on success.

    Loud guard: ``html_body`` is sent as the message's HTML part. If it
    contains no HTML markup at all it would be delivered as a plain-looking
    email (exactly the bug where the styled template silently degraded to
    text) -- refuse loudly instead of degrading silently.
    """
    settings = get_settings()
    if not settings.resend_api_key:
        raise EmailSendError("RESEND_API_KEY is not configured")

    if not _HTML_TAG_RE.search(html_body or ""):
        logger.error(
            "[resend.adapter] refusing to send to=%s subject=%r: html_body "
            "contains no HTML markup -- a plain-text body must never be sent "
            "as the HTML part (silent degradation is the bug this guards).",
            to,
            subject,
        )
        raise EmailSendError(
            "html_body contains no HTML markup -- refusing to send it as the "
            "email HTML part (would arrive as plain text)"
        )

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