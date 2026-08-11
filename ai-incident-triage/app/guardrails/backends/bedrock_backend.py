"""AWS Bedrock Guardrails-backed implementation.

Requires `boto3` (not yet a project dependency) and an AWS Bedrock
guardrail ID/version to enforce. When implementing: use boto3's default
credential chain / an IAM role — never hardcode AWS keys in code or
commit them — and add AWS_REGION plus the guardrail ID/version to
.env(.example) alongside the existing LLM provider keys.
"""
from app.guardrails.models import GuardrailContext, GuardrailResult


class BedrockGuardrailBackend:
    def evaluate(self, context: GuardrailContext) -> GuardrailResult:
        raise NotImplementedError
