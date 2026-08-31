"""Assembles the IncidentReport and renders it as human-readable Markdown.

Per the HLD's Formatter step (§15): the canonical Pydantic/JSON object is one
output, but the thing an engineer actually reads is the rendered Markdown --
headed sections, findings/actions as checklists, runbook links as real
links, a visible rule-vs-LLM severity-agreement indicator, and hypotheses
visually distinguished by label so an unconfirmed guess is never mistaken
for a fact.

``build_incident_report``/``render_markdown_report`` below do not call an LLM --
they only assemble/render what the Classification, investigation sub-agents,
and RCA & Report agent (app/agents/rca_report/agent.py) already produced.

``rca_report_service`` at the bottom is the graph-node adapter: it matches the
``(state, deps) -> dict`` calling convention every node in app/graph/nodes/
uses (see rca_report_node's ``deps.get("rca_report_service", _default_rca_report)``),
so injecting it via ``deps`` swaps the node from its rule-based fallback to the
real LLM-backed RCA agent with no change to the graph itself.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.agents.rca_report.agent import generate_root_cause_analysis
from app.domain.models.approval import ApprovalDecision
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import EvidenceCollection
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.incident import Incident
from app.domain.models.report import IncidentReport, RunbookReference
from app.domain.models.root_cause import RootCauseAnalysis
from app.domain.models.verification import VerificationResult
from app.guardrails.validator import validate_step_output

logger = logging.getLogger(__name__)

_LABEL_PREFIX = {
    HypothesisLabel.LIKELY: "Likely cause",
    HypothesisLabel.POSSIBLE: "Possible cause (unconfirmed)",
    HypothesisLabel.UNLIKELY: "Unlikely cause (ruled in for completeness)",
}

_LOW_CONFIDENCE_THRESHOLD = 0.4


def build_incident_report(
    incident_id: str,
    classification: ClassificationResult,
    evidence: EvidenceCollection,
    hypotheses: list[Hypothesis],
    root_cause: RootCauseAnalysis,
    verification: VerificationResult,
    runbook_references: list[RunbookReference] | None = None,
    approval: ApprovalDecision | None = None,
    created_at: datetime | None = None,
) -> IncidentReport:
    """Assemble the canonical IncidentReport from each stage's already-typed output."""
    return IncidentReport(
        incident_id=incident_id,
        classification=classification,
        evidence=evidence,
        hypotheses=hypotheses,
        root_cause=root_cause,
        recommended_actions=_derive_recommended_actions(root_cause, runbook_references or []),
        runbook_references=runbook_references or [],
        verification=verification,
        approval=approval,
        created_at=created_at or datetime.now(UTC),
    )


def _derive_recommended_actions(
    root_cause: RootCauseAnalysis, runbook_references: list[RunbookReference]
) -> list[str]:
    """Deterministic, non-LLM derivation of next steps -- no model call for this.

    Kept intentionally simple: point at the primary cause, any matched
    runbooks, and flag low-confidence RCAs for continued investigation rather
    than immediate remediation.
    """
    actions: list[str] = []
    if root_cause.confidence_score < _LOW_CONFIDENCE_THRESHOLD:
        actions.append(
            "Confidence is low -- continue investigation before acting on this root cause."
        )
    else:
        actions.append(f"Investigate and remediate: {root_cause.primary_cause.description}")
    for factor in root_cause.contributing_factors:
        if factor.label != HypothesisLabel.UNLIKELY:
            actions.append(f"Rule out contributing factor: {factor.description}")
    for ref in runbook_references:
        actions.append(f"Follow runbook: {ref.title} ({ref.url})")
    return actions


def render_markdown_report(report: IncidentReport) -> str:
    """Render ``report`` as the Markdown an engineer actually reads."""
    sections = [
        _render_header(report),
        _render_classification(report.classification),
        _render_evidence(report.evidence),
        _render_hypotheses(report.hypotheses),
        _render_root_cause(report.root_cause),
        _render_recommended_actions(report.recommended_actions),
        _render_runbooks(report.runbook_references),
        _render_verification(report.verification),
    ]
    if report.approval is not None:
        sections.append(_render_approval(report.approval))
    return "\n\n".join(sections) + "\n"


def _render_header(report: IncidentReport) -> str:
    return (
        f"# Incident Report: {report.incident_id}\n\n"
        f"**Generated:** {report.created_at.isoformat()}  \n"
        f"**Report version:** {report.report_version}"
    )


def _render_classification(classification: ClassificationResult) -> str:
    agreement = "(no rule-based floor recorded)"
    if classification.rule_based_priority is not None:
        agreement = (
            f"✅ Matches rule-based floor ({classification.rule_based_priority.value})"
            if classification.agrees_with_rule
            else (
                "⚠️ Escalated above rule-based floor "
                f"(rule floor: {classification.rule_based_priority.value}, "
                f"final: {classification.priority.value})"
            )
        )
    services = ", ".join(classification.affected_services) or "(none)"
    teams = ", ".join(t.value for t in classification.suggested_teams) or "(none)"
    return (
        "## Classification\n\n"
        f"- **Type:** {classification.incident_type.value}\n"
        f"- **Priority:** {classification.priority.value} -- {agreement}\n"
        f"- **Confidence:** {classification.confidence:.2f}\n"
        f"- **Affected services:** {services}\n"
        f"- **Suggested teams:** {teams}\n"
        f"- **Reasoning:** {classification.reasoning}"
    )


def _render_evidence(evidence: EvidenceCollection) -> str:
    if not evidence.items:
        findings = "_(no evidence collected)_"
    else:
        findings = "\n".join(
            f"{i}. [x] **{item.source}** ({item.severity}): {item.finding} "
            f"<sub>`{item.evidence_id}`</sub>"
            for i, item in enumerate(evidence.items, start=1)
        )
    return f"## Investigation Findings\n\n{evidence.summary}\n\n{findings}"


def _render_hypotheses(hypotheses: list[Hypothesis]) -> str:
    if not hypotheses:
        return "## Hypotheses\n\n_(none proposed)_"
    lines = "\n".join(f"- {_format_hypothesis(h)}" for h in hypotheses)
    return f"## Hypotheses\n\n{lines}"


def _format_hypothesis(hypothesis: Hypothesis) -> str:
    prefix = _LABEL_PREFIX[hypothesis.label]
    return f"*{prefix}:* {hypothesis.description} (confidence {hypothesis.confidence:.2f})"


def _render_root_cause(root_cause: RootCauseAnalysis) -> str:
    contributing = (
        "\n".join(f"- {_format_hypothesis(h)}" for h in root_cause.contributing_factors)
        or "_(none)_"
    )
    timeline = (
        "\n".join(f"{i}. {e.timestamp} -- {e.description}" for i, e in enumerate(root_cause.timeline, start=1))
        or "_(no timeline reconstructed)_"
    )
    components = ", ".join(root_cause.affected_components) or "(none)"
    return (
        "## Root Cause Analysis\n\n"
        f"**Primary cause:** {_format_hypothesis(root_cause.primary_cause)}\n\n"
        f"**Confidence score:** {root_cause.confidence_score:.2f}\n\n"
        f"**Contributing factors:**\n{contributing}\n\n"
        f"**Affected components:** {components}\n\n"
        f"**Timeline:**\n{timeline}"
    )


def _render_recommended_actions(actions: list[str]) -> str:
    if not actions:
        return "## Recommended Actions\n\n_(none)_"
    lines = "\n".join(f"- [ ] {action}" for action in actions)
    return f"## Recommended Actions\n\n{lines}"


def _render_runbooks(runbook_references: list[RunbookReference]) -> str:
    if not runbook_references:
        return "## Related Runbooks\n\n_(none matched)_"
    lines = "\n".join(f"- [{ref.title}]({ref.url})" for ref in runbook_references)
    return f"## Related Runbooks\n\n{lines}"


def _render_verification(verification: VerificationResult) -> str:
    status = "✅ Resolved" if verification.is_resolved else "❌ Not resolved"
    lines = [f"## Verification\n\n- **Status:** {status}"]
    if verification.resolution_evidence:
        lines.append(f"- **Resolution evidence:** {verification.resolution_evidence}")
    if verification.needs_reinvestigation:
        hints = ", ".join(verification.reinvestigation_hints) or "(none given)"
        lines.append(f"- **Needs reinvestigation:** yes -- {hints}")
    return "\n".join(lines)


def _render_approval(approval: ApprovalDecision) -> str:
    decision = "✅ Approved" if approval.approved else "❌ Rejected"
    return (
        "## Approval\n\n"
        f"- **Decision:** {decision}\n"
        f"- **Reviewer:** {approval.reviewer}\n"
        f"- **Comments:** {approval.comments}\n"
        f"- **Timestamp:** {approval.timestamp.isoformat()}"
    )


def rca_report_service(state: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Graph-node adapter for ``deps["rca_report_service"]``.

    Drop-in replacement for ``app.graph.nodes.rca_report._default_rca_report``
    that uses the real LLM-backed RCA agent instead of picking the top
    hypothesis by raw confidence.
    """
    incident: Incident = state["incident"]
    classification: ClassificationResult = state["classification"]
    evidence_items = state.get("evidence", [])
    hypotheses = state.get("hypotheses", [])
    summary = state.get("investigation_summary") or {}
    evidence = EvidenceCollection(
        items=evidence_items,
        summary=summary.get("summary", f"{len(evidence_items)} evidence item(s) collected"),
    )

    root_cause = generate_root_cause_analysis(
        incident, classification, evidence, hypotheses, model=deps.get("rca_model")
    )

    guardrail_findings = list(state.get("guardrail_findings", []))
    citation_result = validate_step_output(
        "rca_report",
        content=json.dumps(sorted(_cited_evidence_ids(root_cause))),
        metadata={"valid_ids": sorted(e.evidence_id for e in evidence_items)},
    )
    if not citation_result.passed:
        logger.warning(
            "[rca_report_service] citation-existence guardrail flagged incident=%s findings=%s",
            state.get("incident_id"),
            citation_result.findings,
        )
        guardrail_findings.append(
            {
                "node": citation_result.node_name,
                "check": "validate_step_output",
                "passed": citation_result.passed,
                "findings": citation_result.findings,
            }
        )

    report = build_incident_report(
        incident_id=state.get("incident_id") or incident.incident_id,
        classification=classification,
        evidence=evidence,
        hypotheses=hypotheses,
        root_cause=root_cause,
        verification=VerificationResult(is_resolved=False, needs_reinvestigation=True),
    )
    expected_outcome = {
        "expectation": f"Incident resolved by addressing '{root_cause.primary_cause.description}'.",
        "action": f"Apply the recommended fix for '{root_cause.primary_cause.description}' and confirm recovery.",
    }
    return {
        "root_cause": root_cause,
        "rca_confidence": root_cause.confidence_score,
        "incident_report": report,
        "expected_outcome": expected_outcome,
        "guardrail_findings": guardrail_findings,
    }


def _cited_evidence_ids(root_cause: RootCauseAnalysis) -> set[str]:
    """Every evidence id the RCA report claims to cite -- the citation-
    existence guardrail verifies each of these actually exists in this run's
    evidence collection (catches hallucinated citations).
    """
    ids: set[str] = set()
    for hypothesis in [root_cause.primary_cause, *root_cause.contributing_factors]:
        ids.update(hypothesis.supporting_evidence)
        ids.update(hypothesis.contradicting_evidence)
    return ids
