"""Extracts the typed KubernetesAnalysisResult from a structured-agent invocation."""
from __future__ import annotations

from typing import Any, List
from pydantic import BaseModel

from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis

class KubernetesAnalysisResult(BaseModel):
    evidence: List[Evidence]
    hypotheses: List[Hypothesis]
    summary: str

def parse_kubernetes_response(agent_response: dict[str, Any]) -> KubernetesAnalysisResult:
    structured = agent_response.get("structured_response")
    # For LangChain create_structured_agent with response_format, the result is sometimes returned under a different key or directly.
    # But following the classification agent parser pattern:
    if not isinstance(structured, KubernetesAnalysisResult):
        # Fallback if the structured agent returns it directly or under a different key
        if isinstance(agent_response, dict) and "evidence" in agent_response:
            return KubernetesAnalysisResult(**agent_response)
        raise TypeError(
            "Kubernetes agent did not return a structured_response of type "
            f"KubernetesAnalysisResult (got {type(structured)!r})."
        )
    return structured
