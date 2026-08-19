import json
from pydantic import BaseModel
from typing import List

from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis

class LogAnalysisResult(BaseModel):
    evidence: List[Evidence]
    hypotheses: List[Hypothesis]
    summary: str

def parse_log_analysis_response(raw_text: str) -> LogAnalysisResult:
    """Parse the LLM response into LogAnalysisResult."""
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
        return LogAnalysisResult(**data)
    except Exception as e:
        return LogAnalysisResult(
            evidence=[],
            hypotheses=[],
            summary=f"Failed to parse LLM response: {str(e)}"
        )
