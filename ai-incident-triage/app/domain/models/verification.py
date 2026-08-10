from pydantic import BaseModel, Field


class Verification(BaseModel):
    """Result of the verification step: resolved vs. unresolved."""

    resolved: bool = False
    notes: str = ""
    attempts: int = Field(default=1, ge=1)
