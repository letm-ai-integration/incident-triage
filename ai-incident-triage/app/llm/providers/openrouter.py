# OpenRouter provider.
#
# OpenRouter exposes an OpenAI-compatible API, so this provider builds on the
# existing OpenAI-compatible stack already used by the project
# (langchain-openai's ChatOpenAI and the openai SDK). It owns everything
# OpenRouter-specific:
#
#   - the fixed OpenRouter endpoint (not configurable via the environment)
#   - the OpenRouter API key
#   - the default OpenRouter model (config.openrouter_model)
#   - OpenAI-compatible client / chat-model initialization
#
# It must NOT contain agent prompts, agent tools, business logic, or graph/node
# logic. Agents consume this provider through app/llm/client.py and never see
# the endpoint, the API key, or the underlying client setup.
from typing import Any

from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI, OpenAI
from pydantic import SecretStr

from app.config import settings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterConfigurationError(RuntimeError):
    """Raised when OpenRouter is not configured correctly."""


def _require_api_key() -> str:
    api_key = settings.openrouter_api_key
    if not api_key:
        raise OpenRouterConfigurationError("OPENROUTER_API_KEY is not configured.")
    return api_key


def get_client(**kwargs: Any) -> OpenAI:
    """Build a low-level OpenAI-compatible client pointed at OpenRouter."""
    return OpenAI(api_key=_require_api_key(), base_url=OPENROUTER_BASE_URL, **kwargs)


def get_async_client(**kwargs: Any) -> AsyncOpenAI:
    """Build an async OpenAI-compatible client pointed at OpenRouter."""
    return AsyncOpenAI(
        api_key=_require_api_key(), base_url=OPENROUTER_BASE_URL, **kwargs
    )


def get_chat_model(
    model: str | None = None, temperature: float = 0, **kwargs: Any
) -> ChatOpenAI:
    """Build the OpenRouter chat model.

    ``model`` takes precedence over the configured default
    (``config.openrouter_model``). Passes through any extra LangChain chat-model
    kwargs (e.g. ``max_retries``, ``default_headers``).
    """
    resolved_model = model or settings.openrouter_model
    return ChatOpenAI(
        model=resolved_model,
        api_key=SecretStr(_require_api_key()),
        base_url=OPENROUTER_BASE_URL,
        temperature=temperature,
        **kwargs,
    )
