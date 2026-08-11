# Provider dispatch layer.
#
# The factory owns provider selection. Providers live under
# app/llm/providers/ and each exposes ``get_chat_model(model, temperature,
# **kwargs)``. OpenRouter is the default provider used by the centralized
# client (app/llm/client.py); the other providers remain registered for
# backward compatibility but are not yet implemented.
#
#   get_llm()               -> OpenRouter chat model (default provider)
#   get_llm("openrouter")   -> OpenRouter chat model
#   get_llm("openai", ...)  -> OpenAI provider (registered, not yet implemented)
import importlib
from typing import Any

_PROVIDER_MODULES: dict[str, str] = {
    "openrouter": "app.llm.providers.openrouter",
    "openai": "app.llm.providers.openai",
    "anthropic": "app.llm.providers.anthropic",
    "groq": "app.llm.providers.groq",
    "gemini": "app.llm.providers.gemini",
}

_DEFAULT_PROVIDER = "openrouter"


def get_llm(
    provider: str = _DEFAULT_PROVIDER,
    model: str | None = None,
    temperature: float = 0,
    **kwargs: Any,
):
    """Return the chat model for the requested provider.

    ``provider`` is a key in ``_PROVIDER_MODULES``. The provider module's
    ``get_chat_model`` factory is used so OpenRouter integrates through the same
    mechanism as the existing providers.
    """
    module_name = _PROVIDER_MODULES.get(provider)
    if module_name is None:
        known = ", ".join(sorted(_PROVIDER_MODULES))
        raise ValueError(f"Unknown LLM provider {provider!r}. Known providers: {known}")

    module = importlib.import_module(module_name)
    factory_fn = getattr(module, "get_chat_model", None)
    if factory_fn is None:
        raise NotImplementedError(
            f"LLM provider {provider!r} is registered but does not implement get_chat_model() yet"
        )
    return factory_fn(model=model, temperature=temperature, **kwargs)
