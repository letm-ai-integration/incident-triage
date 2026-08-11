# Centralized LLM client.
#
# Application-facing utility layer that hides OpenRouter configuration, API key
# loading, model initialization, provider-specific setup, and common agent
# creation. Agents use this module and never touch the provider internals:
#
#   from app.llm.client import create_agent
#
#   agent = create_agent(system_prompt=SYSTEM_PROMPT, tools=TOOLS)
#
# This module must NOT contain business logic, agent-specific prompts, or
# agent-specific tools. It delegates to app/llm/factory.py (provider selection)
# and the provider layer, keeping only thin, reusable helpers.
#
# Layering: config.py -> client.py -> factory.py -> providers/openrouter.py.
from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent as _create_agent

from app.config import settings
from app.llm import factory
from app.llm.providers import openrouter

__all__ = [
    "async_chat_completion",
    "chat_completion",
    "create_agent",
    "create_structured_agent",
    "get_chat_model",
    "get_client",
]


def get_client() -> Any:
    """Return a low-level OpenAI-compatible client pointed at OpenRouter.

    Delegates to the OpenRouter provider so the endpoint/key configuration stays
    in a single infrastructure place.
    """
    return openrouter.get_client()


def get_chat_model(model: str | None = None, temperature: float = 0, **kwargs: Any):
    """Return the OpenRouter chat model.

    ``model`` supplied -> use it; otherwise use ``config.openrouter_model``
    (default ``deepseek/deepseek-v4-flash``).
    """
    return factory.get_llm(
        provider="openrouter", model=model, temperature=temperature, **kwargs
    )


def create_agent(
    system_prompt: str,
    tools: Sequence[Any] | None = None,
    model: str | None = None,
    **kwargs: Any,
):
    """Create a ReAct-style agent backed by the OpenRouter chat model.

    Uses the project's LangChain agent factory (``langchain.agents.create_agent``).
    The explicit ``model`` overrides the configured default; extra kwargs pass
    through to the agent factory.
    """
    return _create_agent(
        model=get_chat_model(model=model),
        tools=list(tools) if tools else [],
        system_prompt=system_prompt,
        **kwargs,
    )


def create_structured_agent(
    system_prompt: str,
    output_schema: Any,
    model: str | None = None,
    **kwargs: Any,
):
    """Create an agent whose final response conforms to ``output_schema``.

    Wraps the existing agent factory and passes the schema through its native
    ``response_format`` support (the project's structured-output mechanism) so
    no schema parsing/validation logic is duplicated here.
    """
    return _create_agent(
        model=get_chat_model(model=model),
        tools=[],
        system_prompt=system_prompt,
        response_format=output_schema,
        **kwargs,
    )


def _resolve_model(model: str | None) -> str:
    return model or settings.openrouter_model


def chat_completion(
    messages: Sequence[Any], model: str | None = None, **kwargs: Any
) -> Any:
    """Make a synchronous OpenAI-compatible chat completion via OpenRouter.

    Reuses ``get_client()`` so authentication/provider setup is not duplicated.
    """
    return get_client().chat.completions.create(
        model=_resolve_model(model),
        messages=list(messages),
        **kwargs,
    )


async def async_chat_completion(
    messages: Sequence[Any], model: str | None = None, **kwargs: Any
) -> Any:
    """Make an async OpenAI-compatible chat completion via OpenRouter.

    Uses the async OpenRouter client so the event loop is never blocked.
    """
    async_client = openrouter.get_async_client()
    return await async_client.chat.completions.create(
        model=_resolve_model(model),
        messages=list(messages),
        **kwargs,
    )
