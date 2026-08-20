"""Tests for the Resend email adapter.

The ``resend`` SDK module is mocked at the adapter boundary -- no real API
calls are ever made.
"""
import pytest

from app.config import settings
from app.tools.adapters import resend_email as resend_module
from app.tools.adapters.resend_email import EmailSendError, send_email


@pytest.fixture
def resend_config(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "resend_from_email", "alerts@example.com")
    monkeypatch.setattr(settings, "resend_from_name", "Incident Triage Bot")


class _FakeEmails:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []

    def send(self, params):
        self.calls.append(params)
        if self._error is not None:
            raise self._error
        return self._response


def _fake_response(message_id="msg-123"):
    return {"id": message_id}


def test_send_email_calls_sdk_with_configured_from(monkeypatch, resend_config):
    fake = _FakeEmails(response=_fake_response("msg-abc"))
    monkeypatch.setattr(resend_module.resend, "Emails", fake)

    message_id = send_email("dev@example.com", "Subject line", "<p>body</p>")

    assert message_id == "msg-abc"
    assert fake.calls == [
        {
            "from": "Incident Triage Bot <alerts@example.com>",
            "to": ["dev@example.com"],
            "subject": "Subject line",
            "html": "<p>body</p>",
        }
    ]
    assert resend_module.resend.api_key == "re_test_key"


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", None)

    with pytest.raises(EmailSendError, match="RESEND_API_KEY is not configured"):
        send_email("dev@example.com", "subject", "<p>body</p>")


def test_sdk_failure_raises_emailsenderror(monkeypatch, resend_config):
    fake = _FakeEmails(error=RuntimeError("connection refused"))
    monkeypatch.setattr(resend_module.resend, "Emails", fake)

    with pytest.raises(EmailSendError, match="Failed to send email via Resend"):
        send_email("dev@example.com", "subject", "<p>body</p>")