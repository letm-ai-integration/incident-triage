# Centralized application configuration.
#
# The project uses pydantic-settings. Environment variables are read
# automatically (e.g. ``OPENROUTER_API_KEY`` -> ``openrouter_api_key``) with an
# optional local ``.env`` file. This is the single configuration entry point for
# the LLM stack:
#
#   LLM_PROVIDER            -> settings.llm_provider         -> active provider
#   OPENROUTER_* / GROQ_*   -> per-provider key/model/base URL
#
# Switching ``LLM_PROVIDER`` (default "openrouter") alone changes the provider
# for every agent -- no code changes required.
from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class LLMProvider(str, Enum):
    OPENROUTER = "openrouter"
    GROQ = "groq"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: LLMProvider = LLMProvider.OPENROUTER

    openrouter_api_key: str | None = None
    openrouter_model: str = "deepseek/deepseek-v4-flash"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    llm_temperature: float = 0.2
    llm_max_tokens: int = 2048
    llm_timeout: int = 60

    def active_llm_config(self) -> dict:
        """Single source of truth for which provider is active and its settings."""
        if self.llm_provider == LLMProvider.GROQ:
            return {
                "api_key": self.groq_api_key,
                "base_url": self.groq_base_url,
                "model": self.groq_model,
            }
        return {
            "api_key": self.openrouter_api_key,
            "base_url": self.openrouter_base_url,
            "model": self.openrouter_model,
        }


settings = Settings()


def get_settings() -> Settings:
    """Return the application settings singleton."""
    return settings
