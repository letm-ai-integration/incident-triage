"""Shared test fixtures.

Keeps the suite hermetic: even when RESEND_API_KEY is configured in .env,
tests must never perform live email delivery.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _fake_resend_send(monkeypatch: pytest.MonkeyPatch):
    """Stub the Resend adapter so no test sends real emails."""

    def _fake_send(to: str, subject: str, html_body: str) -> str:
        return f"test-message-id-for-{to}"

    monkeypatch.setattr("app.agents.notification.agent.send_email", _fake_send)
