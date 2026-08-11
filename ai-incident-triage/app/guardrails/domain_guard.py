"""Domain/business-rule consistency check (step guardrail)."""
from app.guardrails.factory import get_backend
from app.guardrails.models import GuardrailCheckType, GuardrailContext, GuardrailResult


def check_domain_consistency(node_name: str, content: str) -> GuardrailResult:
    context = GuardrailContext(
        check_type=GuardrailCheckType.DOMAIN,
        node_name=node_name,
        content=content,
    )
    return get_backend(GuardrailCheckType.DOMAIN).evaluate(context)
