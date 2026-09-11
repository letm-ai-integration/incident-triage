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
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

from langchain.agents import create_agent as _create_agent
from langchain_openai import ChatOpenAI
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
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


def get_groq_guard_chat_model() -> ChatOpenAI | None:
    """Chat model for the Llama Guard content-safety check, independent of
    the active ``LLM_PROVIDER``.

    Returns ``None`` when ``GROQ_API_KEY`` isn't set so callers (the content-
    safety guardrail) can fall back to a keyword check instead -- same
    optional-dependency pattern as every other LLM-backed fallback in this
    codebase.
    """
    settings = get_settings()
    if not settings.groq_api_key:
        return None
    return ChatOpenAI(
        model=settings.groq_guard_model,
        api_key=SecretStr(settings.groq_api_key),
        base_url=settings.groq_base_url,
        temperature=0,
        max_tokens=32,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
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


# ---------------------------------------------------------------------------
# Preflight availability check (infrastructure gate, NOT a workflow step).
#
# Config presence ("is there an API key string?") says nothing about whether
# the key is valid or the provider is reachable *right now*. Both entry points
# (CLI + Streamlit) run this once before the graph starts, so a bad key /
# downed provider / network problem short-circuits the run instead of failing
# halfway through and wasting a run.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMPreflightResult:
    """Outcome of the pre-run LLM availability check."""

    ok: bool
    # "" | "not_configured" | "invalid_key" | "unreachable" | "model_error"
    # | "provider_error" -- distinct because the fixes differ.
    reason: str
    message: str  # human-readable, actionable, entry-point-ready


def run_llm_preflight(timeout: int | None = None) -> LLMPreflightResult:
    """Verify the active provider is configured AND reachable via a real call.

    Makes one minimal chat-completion request (``max_tokens=1``, no retries,
    short timeout) so the key, model id, and network path are all exercised.
    Cost is a single token; latency is one round trip (~0.3-1.5 s), once per
    run -- negligible against a multi-node LLM pipeline.
    """
    settings = get_settings()
    cfg = settings.active_llm_config()
    provider = settings.llm_provider.value
    if not cfg["api_key"]:
        return LLMPreflightResult(
            ok=False,
            reason="not_configured",
            message=(
                f"No API key configured for LLM provider '{provider}'. "
                f"Set the provider's API key in .env and retry."
            ),
        )

    effective_timeout = timeout if timeout is not None else min(10, settings.llm_timeout)
    started = time.monotonic()
    try:
        client = OpenAI(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
            timeout=effective_timeout,
            max_retries=0,  # fail fast: retrying a dead provider only adds latency
        )
        client.chat.completions.create(
            model=cfg["model"],
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
    except AuthenticationError:
        return LLMPreflightResult(
            ok=False,
            reason="invalid_key",
            message=(
                f"API key rejected by LLM provider '{provider}' (401 unauthorized). "
                "The key is invalid, revoked, or expired -- fix or replace it in .env."
            ),
        )
    except PermissionDeniedError:
        return LLMPreflightResult(
            ok=False,
            reason="invalid_key",
            message=(
                f"API key is valid but not authorized for model "
                f"'{cfg['model']}' on provider '{provider}' (403). "
                "Grant the key access to this model or pick a model it can use."
            ),
        )
    except (APITimeoutError, APIConnectionError) as exc:
        return LLMPreflightResult(
            ok=False,
            reason="unreachable",
            message=(
                f"LLM provider '{provider}' unreachable ({cfg['base_url']}): "
                f"{type(exc).__name__} -- check network connectivity, the "
                "provider's status page, and the base_url in .env."
            ),
        )
    except NotFoundError:
        return LLMPreflightResult(
            ok=False,
            reason="model_error",
            message=(
                f"LLM provider '{provider}' does not know model '{cfg['model']}' "
                "(404) -- fix the model id in .env."
            ),
        )
    except RateLimitError:
        # 429 proves the key was accepted and the provider is reachable; a
        # transient quota blip is not an infrastructure failure.
        return LLMPreflightResult(
            ok=True,
            reason="",
            message=(
                f"LLM provider '{provider}' reachable (rate-limited, 429 -- "
                "key accepted; expect throttling during the run)."
            ),
        )
    except APIStatusError as exc:
        return LLMPreflightResult(
            ok=False,
            reason="provider_error",
            message=(
                f"LLM provider '{provider}' returned HTTP {exc.status_code} on "
                f"the preflight call -- the provider is up but erroring "
                f"({type(exc).__name__}). Retry shortly or check its status page."
            ),
        )
    except Exception as exc:  # noqa: BLE001 -- gate must classify any failure
        return LLMPreflightResult(
            ok=False,
            reason="provider_error",
            message=(
                f"LLM provider '{provider}' preflight call failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "[llm.client] preflight ok provider=%s model=%s in %sms",
        provider,
        cfg["model"],
        elapsed_ms,
    )
    return LLMPreflightResult(
        ok=True,
        reason="",
        message=(
            f"LLM provider '{provider}' reachable; model '{cfg['model']}' "
            f"responded ({elapsed_ms} ms)."
        ),
    )


__all__ = [
    "LLM",
    "LLMPreflightResult",
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
    "get_groq_guard_chat_model",
    "run_llm_preflight",
]