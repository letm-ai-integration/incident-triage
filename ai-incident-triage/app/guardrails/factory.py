"""Dispatches each guardrail check to its configured backend.

Mirrors the pluggable-provider pattern planned for app/llm/factory.py:
this is the only file that needs to change to add a new framework or
repoint a check to a different one.
"""
from app.guardrails.backends.bedrock_backend import BedrockGuardrailBackend
from app.guardrails.backends.custom_backend import CustomGuardrailBackend
from app.guardrails.backends.nemo_backend import NemoGuardrailBackend
from app.guardrails.base import GuardrailBackend
from app.guardrails.config import get_backend_name
from app.guardrails.models import GuardrailCheckType

_REGISTRY: dict[str, type[GuardrailBackend]] = {
    "custom": CustomGuardrailBackend,
    "nemo": NemoGuardrailBackend,
    "bedrock": BedrockGuardrailBackend,
}


def get_backend(check_type: GuardrailCheckType) -> GuardrailBackend:
    backend_name = get_backend_name(check_type)
    return _REGISTRY[backend_name]()
