"""Extracts the typed ClassificationResult from a structured-agent invocation."""
from __future__ import annotations

from typing import Any

from app.domain.models.classification import ClassificationResult


def parse_classification_response(agent_response: dict[str, Any]) -> ClassificationResult:
    structured = agent_response.get("structured_response")
    if not isinstance(structured, ClassificationResult):
        raise TypeError(
            "Classification agent did not return a structured_response of type "
            f"ClassificationResult (got {type(structured)!r})."
        )
    return structured
