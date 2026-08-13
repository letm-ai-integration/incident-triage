from typing import List, Optional
from pydantic import BaseModel, Field

from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis
from app.llm.structured_output import StructuredOutputParser, OutputParsingError
from app.utils.logger import get_logger

logger = get_logger(__name__)

class LogAnalysisResult(BaseModel):
    evidence: List[Evidence] = Field(default_factory=list)
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    summary: str

def parse_log_analysis_response(raw_text: str) -> LogAnalysisResult:
    """
    Parses the raw LLM output into a LogAnalysisResult.
    Handles parsing failures by returning a minimal fallback result.
    """
    try:
        return StructuredOutputParser.parse(raw_text, LogAnalysisResult)
    except OutputParsingError as e:
        logger.error(f"Failed to parse log analysis response: {e}")
        # Return fallback
        return LogAnalysisResult(
            evidence=[
                Evidence(
                    evidence_id="LOG-PARSE-ERROR",
                    source="log_analysis",
                    finding="LLM analysis completed but output could not be parsed.",
                    severity="LOW",
                    raw_data={"error": str(e), "raw_text_snippet": raw_text[:200]}
                )
            ],
            hypotheses=[],
            summary="Log analysis encountered a parsing error."
        )
