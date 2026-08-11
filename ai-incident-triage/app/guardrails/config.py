"""Per-check backend selection.

Defaults every check to the dependency-free "custom" backend. Wire this
into app/config.py (currently also an empty stub) once that module exists,
the same way LLM provider selection is meant to be config-driven per agent.
"""
from app.guardrails.models import GuardrailCheckType

DEFAULT_BACKENDS: dict[GuardrailCheckType, str] = {
    GuardrailCheckType.DOMAIN: "custom",
    GuardrailCheckType.PII: "custom",
    GuardrailCheckType.SAFETY: "custom",
    GuardrailCheckType.PROMPT_INJECTION: "custom",
    GuardrailCheckType.SCHEMA_VALIDATION: "custom",
    GuardrailCheckType.FINAL_REVIEW: "custom",
}


def get_backend_name(check_type: GuardrailCheckType) -> str:
    return DEFAULT_BACKENDS[check_type]
