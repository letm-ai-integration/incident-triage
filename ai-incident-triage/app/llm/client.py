"""
Provider-agnostic LLM client.

Every agent, service, or graph node MUST import LLM helpers from here.
No agent, service, or node may import ``openai``, ``groq``, or any provider
SDK directly -- see rules in the migration spec.

The active provider (OpenRouter by default, or Groq) is selected purely via
``.env`` (``LLM_PROVIDER``). OpenRouter and Groq both expose OpenAI-compatible
chat-completions APIs, so a single implementation pointed at a different
``base_url`` + ``api_key`` + ``model`` covers both -- no per-provider branching
beyond config resolution.

This module also preserves the project's LangChain agent helpers
(``create_agent`` / ``create_structured_agent``), which are provider-agnostic
now that they build the chat model from the active provider config.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

from langchain.agents import create_agent as _create_agent
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel, SecretStr

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class LLMConfigurationError(RuntimeError):
    """Raised when the active LLM provider is not configured correctly."""


@dataclass(frozen=True)
class _ProviderConfig:
    api_key: str
    base_url: str
    model: str


def _resolve_provider_config() -> _ProviderConfig:
    settings = get_settings()
    cfg = settings.active_llm_config()
    if not cfg["api_key"]:
        raise LLMConfigurationError(
            f"Missing API key for active LLM provider '{settings.llm_provider.value}'. "
            "Set it in .env."
        )
    logger.info(
        "[llm.client] resolved provider=%s base_url=%s model=%s api_key=***%s timeout=%ss",
        settings.llm_provider.value,
        cfg["base_url"],
        cfg["model"],
        cfg["api_key"][-4:],
        settings.llm_timeout,
    )
    return _ProviderConfig(api_key=cfg["api_key"], base_url=cfg["base_url"], model=cfg["model"])


def get_client(**kwargs: Any) -> OpenAI:
    """Low-level OpenAI-compatible client for the active provider.

    Internal helper -- prefer ``create_llm()`` / ``create_agent()`` / chat
    completion helpers in agent code.
    """
    cfg = _resolve_provider_config()
    return OpenAI(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        timeout=get_settings().llm_timeout,
        max_retries=get_settings().llm_max_retries,
        **kwargs,
    )


def get_async_client(**kwargs: Any) -> AsyncOpenAI:
    """Async OpenAI-compatible client for the active provider."""
    cfg = _resolve_provider_config()
    return AsyncOpenAI(
        api_key=cfg.api_key, base_url=cfg.base_url, timeout=get_settings().llm_timeout, **kwargs
    )


def get_chat_model(model: str | None = None, temperature: float | None = None, **kwargs: Any) -> ChatOpenAI:
    """LangChain chat model for the active provider.

    ``model`` supplied -> use it; otherwise use the active provider's configured
    default model. Both supported providers are OpenAI-compatible, so
    ``ChatOpenAI`` pointed at the active provider's ``base_url`` covers both.
    """
    cfg = _resolve_provider_config()
    resolved_model = model or cfg.model
    settings = get_settings()
    if temperature is None:
        temperature = settings.llm_temperature
    logger.debug(
        "[llm.client] creating ChatOpenAI model=%s base_url=%s temperature=%s max_tokens=%s max_retries=%s",
        resolved_model, cfg.base_url, temperature, settings.llm_max_tokens, settings.llm_max_retries,
    )
    return ChatOpenAI(
        model=resolved_model,
        api_key=SecretStr(cfg.api_key),
        base_url=cfg.base_url,
        temperature=temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
        **kwargs,
    )


@dataclass
class LLM:
    """Thin provider-agnostic handle exposing raw chat-completion calls."""

    client: OpenAI
    model: str
    temperature: float
    max_tokens: int

    def invoke(self, messages: list[dict], tools: list[dict] | None = None, **kwargs) -> Any:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=tools,
            **kwargs,
        )
        return response.choices[0].message

    def invoke_structured(self, messages: list[dict], response_model: type[T]) -> T:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        return response_model.model_validate(json.loads(raw))


def create_llm(
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLM:
    """Provider-agnostic LLM handle. Reads the active provider from .env."""
    cfg = _resolve_provider_config()
    settings = get_settings()
    return LLM(
        client=get_client(),
        model=model or cfg.model,
        temperature=temperature if temperature is not None else settings.llm_temperature,
        max_tokens=max_tokens or settings.llm_max_tokens,
    )


def bind_tools(llm: LLM, tools: list[dict]) -> Callable[[list[dict]], Any]:
    """Return a callable that always invokes the LLM with the given tool schema bound."""

    def _call(messages: list[dict]) -> Any:
        return llm.invoke(messages, tools=tools)

    return _call


def create_agent(
    system_prompt: str,
    tools: Sequence[Any] | None = None,
    model: str | None = None,
    temperature: float | None = None,
    **kwargs: Any,
):
    """Create a ReAct-style agent backed by the active provider's chat model.

    Uses the project's LangChain agent factory (``langchain.agents.create_agent``).
    The explicit ``model`` overrides the configured default; extra kwargs pass
    through to the agent factory.
    """
    return _create_agent(
        model=get_chat_model(model=model, temperature=temperature),
        tools=list(tools) if tools else [],
        system_prompt=system_prompt,
        **kwargs,
    )


def create_structured_agent(
    system_prompt: str,
    output_schema: Any,
    model: str | None = None,
    temperature: float | None = None,
    **kwargs: Any,
):
    """Create an agent whose final response conforms to ``output_schema``.

    Wraps the existing agent factory and passes the schema through its native
    ``response_format`` support (the project's structured-output mechanism) so
    no schema parsing/validation logic is duplicated here.
    """
    return _create_agent(
        model=get_chat_model(model=model, temperature=temperature),
        tools=[],
        system_prompt=system_prompt,
        response_format=output_schema,
        **kwargs,
    )


def _resolve_model(model: str | None) -> str:
    return model or _resolve_provider_config().model


def chat_completion(messages: Sequence[Any], model: str | None = None, **kwargs: Any) -> Any:
    """Make a synchronous OpenAI-compatible chat completion via the active provider."""
    return get_client().chat.completions.create(
        model=_resolve_model(model),
        messages=list(messages),
        **kwargs,
    )


async def async_chat_completion(messages: Sequence[Any], model: str | None = None, **kwargs: Any) -> Any:
    """Make an async OpenAI-compatible chat completion via the active provider."""
    async_client = get_async_client()
    return await async_client.chat.completions.create(
        model=_resolve_model(model),
        messages=list(messages),
        **kwargs,
    )


__all__ = [
    "LLM",
    "LLMConfigurationError",
    "async_chat_completion",
    "bind_tools",
    "chat_completion",
    "create_agent",
    "create_llm",
    "create_structured_agent",
    "get_async_client",
    "get_chat_model",
    "get_client",
]