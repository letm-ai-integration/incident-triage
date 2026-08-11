"""Cross-agent consistency and unsupported-claim checks backing the Final
Reviewer (HLD §14.2). This module only owns the pluggable-backend
evaluation; the Final Reviewer agent/graph node itself — wherever the team
builds it — imports run_final_review() rather than calling a backend
directly.
"""
from app.guardrails.factory import get_backend
from app.guardrails.models import (
    FinalReviewResult,
    GuardrailCheckType,
    GuardrailContext,
)


def run_final_review(report_content: str) -> FinalReviewResult:
    context = GuardrailContext(
        check_type=GuardrailCheckType.FINAL_REVIEW,
        node_name="final_reviewer",
        content=report_content,
    )
    result = get_backend(GuardrailCheckType.FINAL_REVIEW).evaluate(context)
    return FinalReviewResult(
        passed=result.passed,
        issues_found=result.findings,
        agent_to_rerun=None,
    )
