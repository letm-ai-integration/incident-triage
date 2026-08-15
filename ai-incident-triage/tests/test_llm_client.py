"""Tests for the provider-agnostic LLM client.

These tests never require a real API key and never make network calls;
provider/client construction is local and completion calls are mocked.
"""

import asyncio
import importlib

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
    ):
        assert hasattr(pkg, name)