"""Tests for the OpenRouter provider and the centralized LLM client.

These tests never require a real OpenRouter API key and never make network
calls; provider/client construction is local and completion calls are mocked.
"""

import asyncio
import importlib

import pytest
from langchain_core.tools import tool
from pydantic import BaseModel

from app.config import Settings, settings
from app.llm import client
from app.llm.providers import openrouter
from app.llm.providers.openrouter import (
    OPENROUTER_BASE_URL,
    OpenRouterConfigurationError,
    get_chat_model,
    get_client,
)


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "openrouter_model", "deepseek/deepseek-v4-flash")
    return "test-key"


# ---------------------------------------------------------------- config ----


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


def test_no_openrouter_base_url_setting():
    assert "openrouter_base_url" not in Settings.model_fields


# -------------------------------------------------------------- provider ----


def test_openrouter_endpoint_is_fixed():
    assert OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"


def test_provider_get_chat_model_default_model(api_key):
    llm = get_chat_model()
    assert llm.model_name == "deepseek/deepseek-v4-flash"
    assert llm.openai_api_base == OPENROUTER_BASE_URL


def test_provider_get_chat_model_override(api_key):
    llm = get_chat_model(model="anthropic/claude-3.5-sonnet")
    assert llm.model_name == "anthropic/claude-3.5-sonnet"


def test_provider_get_client(api_key):
    openai_client = get_client()
    assert openai_client.api_key == "test-key"
    assert str(openai_client.base_url).rstrip("/") == OPENROUTER_BASE_URL


def test_missing_api_key_raises_clear_error(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    with pytest.raises(
        OpenRouterConfigurationError, match="OPENROUTER_API_KEY is not configured"
    ):
        get_chat_model()
    with pytest.raises(
        OpenRouterConfigurationError, match="OPENROUTER_API_KEY is not configured"
    ):
        get_client()


# ---------------------------------------------------------------- client ----


def test_client_get_chat_model_default_and_override(api_key):
    assert client.get_chat_model().model_name == "deepseek/deepseek-v4-flash"
    assert client.get_chat_model(model="custom/model").model_name == "custom/model"


def test_client_get_chat_model_missing_key(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    with pytest.raises(
        OpenRouterConfigurationError, match="OPENROUTER_API_KEY is not configured"
    ):
        client.get_chat_model()


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
        messages=[{"role": "user", "content": "hi"}], model="some/openrouter-model"
    )
    assert result == "completion"
    assert calls["model"] == "some/openrouter-model"
    assert calls["messages"] == [{"role": "user", "content": "hi"}]


def test_chat_completion_default_model(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "openrouter_model", "deepseek/deepseek-v4-flash")
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

    monkeypatch.setattr(openrouter, "get_async_client", lambda: FakeClient())
    result = asyncio.run(
        client.async_chat_completion(
            [{"role": "user", "content": "hi"}], model="some/openrouter-model"
        )
    )
    assert result == "completion"
    assert calls["model"] == "some/openrouter-model"
    assert calls["messages"] == [{"role": "user", "content": "hi"}]


# ----------------------------------------------------------- factory --------


def test_factory_uses_openrouter_by_default(api_key):
    from app.llm import factory

    llm = factory.get_llm()
    assert llm.model_name == "deepseek/deepseek-v4-flash"


def test_factory_unknown_provider_raises():
    from app.llm import factory

    with pytest.raises(ValueError, match="Unknown LLM provider"):
        factory.get_llm(provider="does-not-exist")


def test_package_exposes_client_api():
    pkg = importlib.import_module("app.llm")
    for name in (
        "get_client",
        "get_chat_model",
        "create_agent",
        "create_structured_agent",
        "chat_completion",
        "async_chat_completion",
    ):
        assert hasattr(pkg, name)
