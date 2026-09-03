"""Tests for the Langfuse callback-handler wiring.

No real Langfuse client/network calls -- the SDK classes are monkeypatched
so these tests stay hermetic.
"""
from dataclasses import dataclass

import app.telemetry.tracing as tracing_module
from app.telemetry.tracing import get_langfuse_callback_handlers


@dataclass
class _FakeSettings:
    langfuse_public_key: str | None
    langfuse_secret_key: str | None
    langfuse_base_url: str = "https://cloud.langfuse.com"


def test_returns_empty_when_unconfigured(monkeypatch):
    monkeypatch.setattr(
        tracing_module, "get_settings", lambda: _FakeSettings(None, None)
    )
    assert get_langfuse_callback_handlers() == []


def test_returns_handler_when_configured(monkeypatch):
    monkeypatch.setattr(
        tracing_module,
        "get_settings",
        lambda: _FakeSettings("pk-test", "sk-test"),
    )
    monkeypatch.setattr(tracing_module, "_langfuse_client_initialized", False)

    calls = {"langfuse_init": None, "handler_init": None}

    class _FakeLangfuse:
        def __init__(self, **kwargs):
            calls["langfuse_init"] = kwargs

    class _FakeCallbackHandler:
        def __init__(self, **kwargs):
            calls["handler_init"] = kwargs

    import langfuse
    import langfuse.langchain

    monkeypatch.setattr(langfuse, "Langfuse", _FakeLangfuse)
    monkeypatch.setattr(langfuse.langchain, "CallbackHandler", _FakeCallbackHandler)

    handlers = get_langfuse_callback_handlers()

    assert len(handlers) == 1
    assert isinstance(handlers[0], _FakeCallbackHandler)
    assert calls["langfuse_init"] == {
        "public_key": "pk-test",
        "secret_key": "sk-test",
        "base_url": "https://cloud.langfuse.com",
    }
    assert calls["handler_init"] == {"public_key": "pk-test"}


def test_missing_credential_returns_empty(monkeypatch):
    monkeypatch.setattr(
        tracing_module,
        "get_settings",
        lambda: _FakeSettings("pk-test", None),
    )
    assert get_langfuse_callback_handlers() == []
