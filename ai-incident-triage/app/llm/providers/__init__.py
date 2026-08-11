# Provider package.
#
# OpenRouter is the implemented provider and is re-exported here for
# convenience. The other provider modules (anthropic, gemini, groq, openai) are
# preserved as part of the existing architecture; they are not yet implemented.
from app.llm.providers.openrouter import (
    OPENROUTER_BASE_URL,
    OpenRouterConfigurationError,
    get_async_client,
    get_chat_model,
    get_client,
)

__all__ = [
    "OPENROUTER_BASE_URL",
    "OpenRouterConfigurationError",
    "get_async_client",
    "get_chat_model",
    "get_client",
]
