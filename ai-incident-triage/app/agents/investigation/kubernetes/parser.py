import json
from pydantic import BaseModel
from typing import List

from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis

class KubernetesAnalysisResult(BaseModel):
    evidence: List[Evidence]
    hypotheses: List[Hypothesis]
    summary: str

def parse_kubernetes_response(raw_text: str) -> KubernetesAnalysisResult:
    """Parse the LLM response into KubernetesAnalysisResult."""
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    try:
        data = json.loads(text)
        return KubernetesAnalysisResult(**data)
    except Exception as e:
        return KubernetesAnalysisResult(
            evidence=[],
            hypotheses=[],
            summary=f"Failed to parse LLM response: {str(e)}"
        )
