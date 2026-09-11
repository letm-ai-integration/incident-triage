"""Tests for the provider-agnostic LLM client.

These tests never require a real API key and never make network calls;
provider/client construction is local and completion calls are mocked.
"""

import asyncio
import importlib
import types

import httpx
import openai
import pytest
from langchain_core.tools import tool
from pydantic import BaseModel

from app.config import LLMProvider, Settings, settings
from app.llm import client
from app.llm.client import LLMConfigurationError


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", LLMProvider.OPENROUTER)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "openrouter_model", "deepseek/deepseek-v4-flash")
    return "test-key"


# ---------------------------------------------------------------- config ----


def test_default_provider_is_openrouter(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert Settings().llm_provider == LLMProvider.OPENROUTER


def test_default_model_is_deepseek_v4_flash(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert Settings().openrouter_model == "deepseek/deepseek-v4-flash"


def test_config_reads_openrouter_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-config-test")
    monkeypatch.setenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
    cfg = Settings()
    assert cfg.openrouter_api_key == "sk-config-test"
    assert cfg.openrouter_model == "deepseek/deepseek-v4-flash"


def test_active_llm_config_openrouter_defaults(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-config-test")
    cfg = Settings().active_llm_config()
    assert cfg["api_key"] == "sk-config-test"
    assert cfg["base_url"] == "https://openrouter.ai/api/v1"
    assert cfg["model"] == "deepseek/deepseek-v4-flash"


def test_active_llm_config_groq(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-config-test")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    cfg = Settings().active_llm_config()
    assert cfg["api_key"] == "gsk-config-test"
    assert cfg["base_url"] == "https://api.groq.com/openai/v1"
    assert cfg["model"] == "llama-3.3-70b-versatile"


def test_openrouter_base_url_is_configurable():
    assert "openrouter_base_url" in Settings.model_fields


# -------------------------------------------------------------- client ----


def test_client_get_chat_model_default_and_override(api_key):
    assert client.get_chat_model().model_name == "deepseek/deepseek-v4-flash"
    assert client.get_chat_model(model="custom/model").model_name == "custom/model"


def test_client_get_chat_model_missing_key(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    with pytest.raises(LLMConfigurationError, match="Missing API key"):
        client.get_chat_model()


def test_client_get_client(api_key):
    openai_client = client.get_client()
    assert openai_client.api_key == "test-key"
    assert str(openai_client.base_url).rstrip("/") == "https://openrouter.ai/api/v1"


def test_same_missing_key_error_across_helpers(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    for call in (client.get_client, client.get_chat_model, client.create_llm):
        with pytest.raises(LLMConfigurationError, match="Missing API key"):
            call()


def test_create_llm_uses_active_provider_config(api_key):
    llm = client.create_llm()
    assert llm.model == "deepseek/deepseek-v4-flash"
    assert llm.temperature == settings.llm_temperature
    assert llm.max_tokens == settings.llm_max_tokens


def test_create_llm_overrides(api_key):
    llm = client.create_llm(model="custom/model", temperature=0.1, max_tokens=100)
    assert llm.model == "custom/model"
    assert llm.temperature == 0.1
    assert llm.max_tokens == 100


def test_llm_invoke(monkeypatch, api_key):
    calls = {}

    class FakeMessage:
        content = "hello"

    class FakeCompletions:
        def create(self, **kwargs):
            calls.update(kwargs)
            return type("R", (), {"choices": [type("C", (), {"message": FakeMessage})]})()

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    monkeypatch.setattr(client, "get_client", lambda: FakeClient())
    llm = client.create_llm()
    result = llm.invoke([{"role": "user", "content": "hi"}])
    assert result.content == "hello"
    assert calls["model"] == "deepseek/deepseek-v4-flash"


def test_llm_invoke_structured(monkeypatch, api_key):
    class Output(BaseModel):
        summary: str

    class FakeMessage:
        content = '{"summary": "ok"}'

    class FakeCompletions:
        def create(self, **kwargs):
            return type("R", (), {"choices": [type("C", (), {"message": FakeMessage})]})()

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    monkeypatch.setattr(client, "get_client", lambda: FakeClient())
    result = client.create_llm().invoke_structured([{"role": "user", "content": "hi"}], Output)
    assert result == Output(summary="ok")


def test_bind_tools(monkeypatch, api_key):
    captured = {}

    def fake_invoke(messages, tools=None, **kwargs):
        captured["tools"] = tools
        return "ok"

    llm = client.create_llm()
    monkeypatch.setattr(llm, "invoke", fake_invoke)
    bound = client.bind_tools(llm, [{"type": "function"}])
    assert bound([]) == "ok"
    assert captured["tools"] == [{"type": "function"}]


def test_create_agent_without_tools(api_key):
    agent = client.create_agent(system_prompt="You are a triage assistant.")
    assert agent is not None
    assert callable(getattr(agent, "invoke", None))


@tool
def _mock_incident_tool(query: str) -> str:
    """Mock tool for tests."""
    return "ok"


def test_create_agent_with_tools(api_key):
    agent = client.create_agent(
        system_prompt="You are a triage assistant.",
        tools=[_mock_incident_tool],
    )
    assert agent is not None


def test_create_agent_forwards_system_prompt(monkeypatch, api_key):
    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return "agent"

    monkeypatch.setattr(client, "_create_agent", fake_create_agent)
    result = client.create_agent(
        system_prompt="hello agent", tools=[_mock_incident_tool]
    )
    assert result == "agent"
    assert captured["system_prompt"] == "hello agent"
    assert captured["tools"] == [_mock_incident_tool]
    assert captured["model"].model_name == "deepseek/deepseek-v4-flash"


def test_create_structured_agent(api_key):
    class ClassificationOutput(BaseModel):
        incident_type: str
        priority: str

    agent = client.create_structured_agent(
        system_prompt="Classify the incident.",
        output_schema=ClassificationOutput,
    )
    assert agent is not None
    assert callable(getattr(agent, "invoke", None))


def test_create_structured_agent_forwards_schema(monkeypatch, api_key):
    class Output(BaseModel):
        summary: str

    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return "agent"

    monkeypatch.setattr(client, "_create_agent", fake_create_agent)
    client.create_structured_agent(system_prompt="Summarize", output_schema=Output)
    assert captured["system_prompt"] == "Summarize"
    assert captured["response_format"] is Output


def test_chat_completion(monkeypatch, api_key):
    calls = {}

    class FakeCompletions:
        def create(self, **kwargs):
            calls.update(kwargs)
            return "completion"

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    monkeypatch.setattr(client, "get_client", lambda: FakeClient())
    result = client.chat_completion(
        messages=[{"role": "user", "content": "hi"}], model="some/model"
    )
    assert result == "completion"
    assert calls["model"] == "some/model"
    assert calls["messages"] == [{"role": "user", "content": "hi"}]


def test_chat_completion_default_model(monkeypatch, api_key):
    calls = {}

    class FakeCompletions:
        def create(self, **kwargs):
            calls.update(kwargs)
            return "completion"

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    monkeypatch.setattr(client, "get_client", lambda: FakeClient())
    client.chat_completion([{"role": "user", "content": "hi"}])
    assert calls["model"] == "deepseek/deepseek-v4-flash"


def test_async_chat_completion(monkeypatch, api_key):
    calls = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            calls.update(kwargs)
            return "completion"

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    monkeypatch.setattr(client, "get_async_client", lambda: FakeClient())
    result = asyncio.run(
        client.async_chat_completion(
            [{"role": "user", "content": "hi"}], model="some/model"
        )
    )
    assert result == "completion"
    assert calls["model"] == "some/model"
    assert calls["messages"] == [{"role": "user", "content": "hi"}]


# ----------------------------------------------------- provider switching ---


def test_switching_provider_changes_llm_config(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", LLMProvider.GROQ)
    monkeypatch.setattr(settings, "groq_api_key", "gsk-test")
    monkeypatch.setattr(settings, "groq_base_url", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(settings, "groq_model", "llama-3.3-70b-versatile")
    assert settings.active_llm_config()["api_key"] == "gsk-test"
    assert settings.active_llm_config()["model"] == "llama-3.3-70b-versatile"


# ------------------------------------------------------------ no factory ----


def test_factory_module_removed():
    with pytest.raises(ImportError):
        importlib.import_module("app.llm.factory")


def test_package_exposes_client_api():
    pkg = importlib.import_module("app.llm")
    for name in (
        "get_client",
        "get_chat_model",
        "create_agent",
        "create_structured_agent",
        "create_llm",
        "bind_tools",
        "chat_completion",
        "async_chat_completion",
        "LLM",
        "LLMConfigurationError",
        "run_llm_preflight",
        "LLMPreflightResult",
    ):
        assert hasattr(pkg, name)


# ------------------------------------------------------------- preflight ----


def _http_error(exc_cls: type, status: int) -> Exception:
    """Build a real openai APIStatusError subclass with an httpx response."""
    request = httpx.Request("POST", "https://provider.test/v1/chat/completions")
    response = httpx.Response(status_code=status, request=request)
    return exc_cls("boom", response=response, body=None)


class _FakeCompletions:
    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc
        self.calls: list[dict] = []

    def create(self, **kwargs):  # noqa: ANN003
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return types.SimpleNamespace(id="preflight-ok")


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeClient:
    """Records constructor kwargs; returns a stub completions endpoint."""

    last_kwargs: dict = {}

    def __init__(self, **kwargs) -> None:
        type(self).last_kwargs = kwargs
        self.chat = _FakeChat(_FakeClient.completions)


def _install(monkeypatch: pytest.MonkeyPatch, exc: Exception | None = None) -> _FakeClient:
    """Point run_llm_preflight at a fake OpenAI client raising ``exc``."""
    _FakeClient.completions = _FakeCompletions(exc)
    monkeypatch.setattr(client, "OpenAI", _FakeClient)
    return _FakeClient


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", LLMProvider.OPENROUTER)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "openrouter_model", "test/model")
    monkeypatch.setattr(settings, "openrouter_base_url", "https://provider.test/v1")
    monkeypatch.setattr(settings, "llm_timeout", 60)


def test_preflight_passes_and_is_cheap(keyed, monkeypatch):
    fake = _install(monkeypatch)
    result = client.run_llm_preflight()
    assert result.ok is True and result.reason == ""
    # Cheap call: no retries, short timeout, exactly 1 token.
    assert fake.last_kwargs["max_retries"] == 0
    assert fake.last_kwargs["timeout"] <= 10
    assert fake.completions.calls[0]["max_tokens"] == 1


def test_preflight_missing_key(keyed, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    result = client.run_llm_preflight()
    assert result.ok is False and result.reason == "not_configured"
    assert "No API key" in result.message


def test_preflight_invalid_key(keyed, monkeypatch):
    _install(monkeypatch, _http_error(openai.AuthenticationError, 401))
    result = client.run_llm_preflight()
    assert result.ok is False and result.reason == "invalid_key"
    assert "401" in result.message


def test_preflight_permission_denied_maps_to_invalid_key(keyed, monkeypatch):
    _install(monkeypatch, _http_error(openai.PermissionDeniedError, 403))
    result = client.run_llm_preflight()
    assert result.ok is False and result.reason == "invalid_key"
    assert "403" in result.message


def test_preflight_rate_limit_counts_as_reachable(keyed, monkeypatch):
    _install(monkeypatch, _http_error(openai.RateLimitError, 429))
    result = client.run_llm_preflight()
    assert result.ok is True  # 429 proves key accepted + provider reachable
    assert "429" in result.message


def test_preflight_timeout_is_unreachable(keyed, monkeypatch):
    request = httpx.Request("POST", "https://provider.test/v1/chat/completions")
    _install(monkeypatch, openai.APITimeoutError(request=request))
    result = client.run_llm_preflight()
    assert result.ok is False and result.reason == "unreachable"


def test_preflight_connection_error_is_unreachable(keyed, monkeypatch):
    request = httpx.Request("POST", "https://provider.test/v1/chat/completions")
    _install(monkeypatch, openai.APIConnectionError(request=request))
    result = client.run_llm_preflight()
    assert result.ok is False and result.reason == "unreachable"
    assert "provider.test" in result.message


def test_preflight_unknown_model(keyed, monkeypatch):
    _install(monkeypatch, _http_error(openai.NotFoundError, 404))
    result = client.run_llm_preflight()
    assert result.ok is False and result.reason == "model_error"


def test_preflight_provider_5xx(keyed, monkeypatch):
    _install(monkeypatch, _http_error(openai.APIStatusError, 503))
    result = client.run_llm_preflight()
    assert result.ok is False and result.reason == "provider_error"
    assert "503" in result.message


def test_preflight_unexpected_exception_classified(keyed, monkeypatch):
    _install(monkeypatch, RuntimeError("dns exploded"))
    result = client.run_llm_preflight()
    assert result.ok is False and result.reason == "provider_error"
    assert "RuntimeError" in result.message
