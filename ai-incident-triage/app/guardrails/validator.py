"""Structural step-guardrail checks: schema validation, citation-existence,
and label-consistency (HLD §14.1), grouped under one check type since they
all validate the shape/integrity of an agent node's output.
"""
from app.guardrails.factory import get_backend
from app.guardrails.models import GuardrailCheckType, GuardrailContext, GuardrailResult


def validate_step_output(node_name: str, content: str) -> GuardrailResult:
    context = GuardrailContext(
        check_type=GuardrailCheckType.SCHEMA_VALIDATION,
        node_name=node_name,
        content=content,
    )
    return get_backend(GuardrailCheckType.SCHEMA_VALIDATION).evaluate(context)
