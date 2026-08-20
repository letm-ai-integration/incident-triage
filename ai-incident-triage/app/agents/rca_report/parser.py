"""Extracts the typed RootCauseAnalysis from a structured-agent invocation."""
from __future__ import annotations

from typing import Any

from app.domain.models.root_cause import RootCauseAnalysis


def parse_rca_response(agent_response: dict[str, Any]) -> RootCauseAnalysis:
    structured = agent_response.get("structured_response")
    if not isinstance(structured, RootCauseAnalysis):
        raise TypeError(
            "RCA agent did not return a structured_response of type "
            f"RootCauseAnalysis (got {type(structured)!r})."
        )
    return structured
