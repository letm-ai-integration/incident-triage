"""Pydantic contracts shared by every guardrail check and backend."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GuardrailCheckType(str, Enum):
    DOMAIN = "domain"
    PII = "pii"
    SAFETY = "safety"
    PROMPT_INJECTION = "prompt_injection"
    SCHEMA_VALIDATION = "schema_validation"
    FINAL_REVIEW = "final_review"


class GuardrailContext(BaseModel):
    """Everything a backend needs to evaluate one check, regardless of framework."""

    check_type: GuardrailCheckType
    node_name: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GuardrailResult(BaseModel):
    """Step-guardrail outcome. Field names match HLD §14's GuardrailResult contract."""

    node_name: str
    passed: bool
    findings: list[str] = Field(default_factory=list)
    triggered_retry: bool = False
    backend_used: str | None = None


class FinalReviewResult(BaseModel):
    """Final Reviewer outcome. Field names match HLD §14.2's FinalReviewResult contract."""

    passed: bool
    issues_found: list[str] = Field(default_factory=list)
    agent_to_rerun: str | None = None
