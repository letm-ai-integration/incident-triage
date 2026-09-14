"""PII detection + redaction (step guardrail)."""
from typing import Any

from app.guardrails.backends.custom_backend import redact_pii as _redact_pii
from app.guardrails.factory import get_backend
from app.guardrails.models import GuardrailCheckType, GuardrailContext, GuardrailResult


def check_pii(node_name: str, content: str, metadata: dict[str, Any] | None = None) -> GuardrailResult:
    context = GuardrailContext(
        check_type=GuardrailCheckType.PII,
        node_name=node_name,
        content=content,
        metadata=metadata or {},
    )
    return get_backend(GuardrailCheckType.PII).evaluate(context)


def redact_pii(text: str) -> str:
    """Mask email addresses, phone numbers, and credit-card-like digit runs
    in ``text`` -- see ``app.guardrails.backends.custom_backend.redact_pii``.
    """
    return _redact_pii(text)
