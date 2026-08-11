"""Default backend: plain Python (regex/keyword + Pydantic-schema) checks.

Zero extra dependencies — this is the backend every check type uses unless
config.py says otherwise. Per HLD §14.3, this covers schema/citation/label
checks and basic content-safety keyword matching for the POC.
"""
from app.guardrails.models import GuardrailContext, GuardrailResult


class CustomGuardrailBackend:
    def evaluate(self, context: GuardrailContext) -> GuardrailResult:
        raise NotImplementedError
