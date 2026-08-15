"""
Structured-output helpers on top of the provider-agnostic LLM client.

Keeps the project's schema-driven parsing contract: agents ask for a Pydantic
model and the adapter produces one. Agent-specific ``parser.py`` files continue
to own any post-hoc validation/repair of the parsed result.
"""
from __future__ import annotations

from typing import Any

from app.llm.client import create_llm


def invoke_structured(
    messages: list[dict],
    response_model: type[Any],
    *,
    model: str | None = None,
    temperature: float | None = None,
) -> Any:
    """Ask the active provider for a JSON object validated against ``response_model``."""
    llm = create_llm(model=model, temperature=temperature)
    return llm.invoke_structured(messages, response_model)


__all__ = ["invoke_structured"]
