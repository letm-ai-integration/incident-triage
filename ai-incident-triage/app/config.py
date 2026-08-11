# Centralized application configuration.
#
# The project uses pydantic-settings. Environment variables are read
# automatically (e.g. ``OPENROUTER_API_KEY`` -> ``openrouter_api_key``) with an
# optional local ``.env`` file. This is the single configuration entry point for
# the LLM stack:
#
#   OPENROUTER_API_KEY  -> settings.openrouter_api_key  -> OpenRouter provider
#   OPENROUTER_MODEL    -> settings.openrouter_model    -> OpenRouter provider
#
# The OpenRouter endpoint is intentionally NOT configurable via the
# environment; it lives inside the provider (app/llm/providers/openrouter.py).
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openrouter_api_key: str = ""
    openrouter_model: str = "deepseek/deepseek-v4-flash"


settings = Settings()


def get_settings() -> Settings:
    """Return the application settings singleton."""
    return settings
