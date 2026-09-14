"""Domain/business-rule consistency check (step guardrail)."""
from typing import Any

from app.guardrails.factory import get_backend
from app.guardrails.models import GuardrailCheckType, GuardrailContext, GuardrailResult


def check_domain_consistency(
    node_name: str, content: str, metadata: dict[str, Any] | None = None
) -> GuardrailResult:
    context = GuardrailContext(
        check_type=GuardrailCheckType.DOMAIN,
        node_name=node_name,
        content=content,
        metadata=metadata or {},
    )
    return get_backend(GuardrailCheckType.DOMAIN).evaluate(context)
