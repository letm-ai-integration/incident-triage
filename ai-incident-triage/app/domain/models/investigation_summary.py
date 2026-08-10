from pydantic import BaseModel, Field

from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis


class InvestigationSummary(BaseModel):
    """Consolidated output of the parallel investigation sub-agents."""

    evidence: list[Evidence] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    summary: str = ""
