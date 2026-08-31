"""Default backend: plain Python (regex/keyword + Pydantic-schema) checks.

Zero extra dependencies for PII / prompt-injection / citation-existence, per
HLD §14.3. Content-safety additionally tries a Llama Guard call via Groq
(also HLD §14.3, "optional") and falls back to a keyword check when
GROQ_API_KEY isn't configured -- same optional-LLM fallback pattern used
throughout this codebase (e.g. investigation_service.py).
"""
from __future__ import annotations

import logging
import re

from app.guardrails.models import GuardrailCheckType, GuardrailContext, GuardrailResult

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{3,4}(?!\d)")
_CREDIT_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")

_PROMPT_INJECTION_PHRASES = [
    "ignore previous instructions",
    "ignore the above",
    "ignore all previous instructions",
    "disregard previous instructions",
    "disregard the above",
    "you are now",
    "new instructions:",
    "system prompt",
    "reveal your prompt",
    "reveal your instructions",
    "act as if",
    "do anything now",
    "jailbreak",
    "override your instructions",
    "pretend you are",
]

_UNSAFE_KEYWORDS = [
    "kill yourself",
    "build a bomb",
    "make a bomb",
    "how to make explosives",
]


class CustomGuardrailBackend:
    def evaluate(self, context: GuardrailContext) -> GuardrailResult:
        handler = _HANDLERS.get(context.check_type)
        if handler is None:
            raise NotImplementedError(f"No custom backend handler for {context.check_type}")
        return handler(context)


def _check_pii(context: GuardrailContext) -> GuardrailResult:
    findings: list[str] = []
    if _EMAIL_RE.search(context.content):
        findings.append("pii:email detected")
    if _CREDIT_CARD_RE.search(context.content):
        findings.append("pii:credit_card_number detected")
    elif _PHONE_RE.search(context.content):
        findings.append("pii:phone_number detected")
    return GuardrailResult(
        node_name=context.node_name,
        passed=not findings,
        findings=findings,
        triggered_retry=False,
        backend_used="custom",
    )


def _check_prompt_injection(context: GuardrailContext) -> GuardrailResult:
    lowered = context.content.lower()
    findings = [phrase for phrase in _PROMPT_INJECTION_PHRASES if phrase in lowered]
    return GuardrailResult(
        node_name=context.node_name,
        passed=not findings,
        findings=[f"prompt_injection: matched phrase {p!r}" for p in findings],
        triggered_retry=False,
        backend_used="custom",
    )


def _check_safety(context: GuardrailContext) -> GuardrailResult:
    from app.llm.client import get_groq_guard_chat_model

    try:
        guard_model = get_groq_guard_chat_model()
    except Exception:
        # Guard model construction is best-effort -- always fall back to the keyword check.
        logger.exception("[custom_backend] failed to build Llama Guard chat model")
        guard_model = None

    if guard_model is not None:
        try:
            return _check_safety_llama_guard(context, guard_model)
        except Exception:
            # Network/provider failure -- fall back to the keyword check.
            logger.exception("[custom_backend] Llama Guard call failed, falling back to keyword check")

    return _check_safety_keyword(context)


def _check_safety_llama_guard(context: GuardrailContext, guard_model) -> GuardrailResult:
    response = guard_model.invoke(
        [{"role": "user", "content": context.content}]
    )
    text = (response.content or "").strip().lower()
    passed = text.startswith("safe")
    findings: list[str] = []
    if not passed:
        findings = [line.strip() for line in text.splitlines() if line.strip()]
    return GuardrailResult(
        node_name=context.node_name,
        passed=passed,
        findings=findings,
        triggered_retry=False,
        backend_used="llama_guard",
    )


def _check_safety_keyword(context: GuardrailContext) -> GuardrailResult:
    lowered = context.content.lower()
    findings = [f"safety: matched keyword {kw!r}" for kw in _UNSAFE_KEYWORDS if kw in lowered]
    return GuardrailResult(
        node_name=context.node_name,
        passed=not findings,
        findings=findings,
        triggered_retry=False,
        backend_used="custom_keyword",
    )


def _check_schema(context: GuardrailContext) -> GuardrailResult:
    """Citation-existence check: every id in ``metadata['cited_ids']`` (or, if
    absent, every id parsed from ``content`` as a JSON list) must be present
    in ``metadata['valid_ids']``.
    """
    import json

    valid_ids = set(context.metadata.get("valid_ids", []))
    cited_ids = context.metadata.get("cited_ids")
    if cited_ids is None:
        try:
            cited_ids = json.loads(context.content)
        except (json.JSONDecodeError, TypeError):
            cited_ids = []

    missing = [cid for cid in cited_ids if cid not in valid_ids]
    findings = [f"citation: {cid!r} not found among this run's evidence/hypothesis ids" for cid in missing]
    return GuardrailResult(
        node_name=context.node_name,
        passed=not findings,
        findings=findings,
        triggered_retry=False,
        backend_used="custom",
    )


_HANDLERS = {
    GuardrailCheckType.PII: _check_pii,
    GuardrailCheckType.PROMPT_INJECTION: _check_prompt_injection,
    GuardrailCheckType.SAFETY: _check_safety,
    GuardrailCheckType.SCHEMA_VALIDATION: _check_schema,
}
