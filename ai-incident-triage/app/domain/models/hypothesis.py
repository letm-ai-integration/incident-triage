from pydantic import BaseModel, Field


class Hypothesis(BaseModel):
    """A candidate explanation for the incident under investigation."""

    description: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
