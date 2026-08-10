from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """A single piece of evidence collected during investigation."""

    source: str = ""
    summary: str = ""
    content: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
