"""NeMo Guardrails-backed implementation.

Requires the `nemoguardrails` package (not yet a project dependency — add
via `uv add nemoguardrails`, or as an optional dependency group, before
implementing) and a rails config describing the policies to enforce. Per
HLD §14.3 this was deliberately postponed: it's meaningfully more setup
than a five-agent POC needs until there are many more policies/teams
contributing rules.
"""
from app.guardrails.models import GuardrailContext, GuardrailResult


class NemoGuardrailBackend:
    def evaluate(self, context: GuardrailContext) -> GuardrailResult:
        raise NotImplementedError
