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
import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
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
    
    # LLM Settings (Groq)
    groq_api_key: str = Field(default="")
    groq_model_name: str = Field(default="llama-3.3-70b-versatile")
    default_llm_provider: str = Field(default="groq")
    
    # Observability
    langchain_tracing_v2: bool = Field(default=True)
    langsmith_api_key: str = Field(default="")
    langsmith_project: str = Field(default="incident-triage-ai")
    
    # App Settings
    knowledge_base_path: str = Field(default="knowledge_base")
    max_investigation_retries: int = Field(default=3)


settings = Settings()

@lru_cache()
def get_settings() -> Settings:
    """Return the application settings singleton."""
    return settings
