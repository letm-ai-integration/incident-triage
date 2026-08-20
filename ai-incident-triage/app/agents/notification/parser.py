"""Extracts the typed email content from a structured-agent invocation."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class NotificationEmail(BaseModel):
    subject: str
    body: str


def parse_notification_response(agent_response: dict[str, Any]) -> NotificationEmail:
    structured = agent_response.get("structured_response")
    if not isinstance(structured, NotificationEmail):
        raise TypeError(
            "Notification agent did not return a structured_response of type "
            f"NotificationEmail (got {type(structured)!r})."
        )
    return structured