"""Extracts the typed LogAnalysisResult from a structured-agent invocation."""
from __future__ import annotations

from typing import Any, List
from pydantic import BaseModel

from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis

class LogAnalysisResult(BaseModel):
    evidence: List[Evidence]
    hypotheses: List[Hypothesis]
    summary: str

def parse_log_analysis_response(agent_response: dict[str, Any]) -> LogAnalysisResult:
    structured = agent_response.get("structured_response")
    if not isinstance(structured, LogAnalysisResult):
        if isinstance(agent_response, dict) and "evidence" in agent_response:
            return LogAnalysisResult(**agent_response)
        raise TypeError(
            "LogAnalysis agent did not return a structured_response of type "
            f"LogAnalysisResult (got {type(structured)!r})."
        )
    return structured
