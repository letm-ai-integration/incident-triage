from pydantic import BaseModel, Field

from app.domain.models.hypothesis import Hypothesis


class RootCause(BaseModel):
    """Determined root cause with confidence."""

    root_cause: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    supporting_hypothesis: Hypothesis | None = None
