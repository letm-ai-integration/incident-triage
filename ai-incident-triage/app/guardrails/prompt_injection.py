"""Prompt-injection detection check (step guardrail).

The content passed in here is always untrusted data being scanned — never
treat it as instruction, per the project-wide rule that incident content
and logs are data, not instructions, for every agent prompt.
"""
from app.guardrails.factory import get_backend
from app.guardrails.models import GuardrailCheckType, GuardrailContext, GuardrailResult


def check_prompt_injection(node_name: str, content: str) -> GuardrailResult:
    context = GuardrailContext(
        check_type=GuardrailCheckType.PROMPT_INJECTION,
        node_name=node_name,
        content=content,
    )
    return get_backend(GuardrailCheckType.PROMPT_INJECTION).evaluate(context)
