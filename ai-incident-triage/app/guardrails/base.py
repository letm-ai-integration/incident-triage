"""The backend abstraction every guardrail framework integration implements.

A single uniform method keeps every backend interchangeable behind the
factory in factory.py, whether it's a plain regex/keyword check, a NeMo
Guardrails rail, or an AWS Bedrock Guardrails call.
"""
from typing import Protocol

from app.guardrails.models import GuardrailContext, GuardrailResult


class GuardrailBackend(Protocol):
    def evaluate(self, context: GuardrailContext) -> GuardrailResult: ...
