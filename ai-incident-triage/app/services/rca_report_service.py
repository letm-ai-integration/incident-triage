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
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import EvidenceCollection
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.incident import Incident
from app.domain.models.report import IncidentReport, RunbookReference
from app.domain.models.root_cause import RootCauseAnalysis
from app.domain.models.verification import VerificationResult
from app.guardrails.validator import validate_step_output
from app.services.evidence_service import validate_hypotheses
from app.services.hypothesis_service import finalize_root_cause

logger = logging.getLogger(__name__)

_LOW_CONFIDENCE_THRESHOLD = 0.4


def build_incident_report(
    incident_id: str,
    classification: ClassificationResult,
    evidence: EvidenceCollection,
    hypotheses: list[Hypothesis],
    root_cause: RootCauseAnalysis,
    verification: VerificationResult,
    runbook_references: list[RunbookReference] | None = None,
    created_at: datetime | None = None,
    incident_title: str | None = None,
    incident_description: str | None = None,
    environment: str | None = None,
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
        created_at=created_at or datetime.now(UTC),
        incident_title=incident_title,
        incident_description=incident_description,
        environment=environment,
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


_NO_RUNBOOK_NOTE = (
    "**Runbook remediation unavailable:** No applicable runbook or validated "
    "remediation procedure was found. The investigation has identified the "
    "observed symptoms and available evidence, but a validated remediation path "
    "is not available. **On-call engineering action is required to determine, "
    "apply, and validate the appropriate fix.**"
)

_IMPORTANT_NOTE = (
    "**Important:** This investigation is limited to analysis and recommendation "
    "unless explicitly stated otherwise. No remediation should be considered "
    "applied unless there is evidence the change was actually executed and validated."
)


def root_cause_determination(root_cause: RootCauseAnalysis) -> str:
    """One of the three allowed RCA states (master Phase 5, rule 2).

    Deterministic mapping from the validated hypothesis label + capped
    confidence -- never an LLM reinterpretation.
    """
    label = root_cause.primary_cause.label
    if label == HypothesisLabel.LIKELY and root_cause.confidence_score >= 0.5:
        return "Confirmed root cause"
    if label == HypothesisLabel.POSSIBLE and root_cause.confidence_score >= 0.4:
        return "Probable root cause"
    return "Root cause could not be conclusively determined"


def root_cause_state_short(root_cause: RootCauseAnalysis) -> str:
    """Short state for the Investigation Status block (rule 6):
    `Confirmed` is independent of remediation status."""
    determination = root_cause_determination(root_cause)
    if determination.startswith("Confirmed"):
        return "Confirmed"
    if determination.startswith("Probable"):
        return "Probable"
    return "Inconclusive"


def remediation_status(report: IncidentReport) -> str:
    """Remediation state (rule 5): `Applied` requires executed+validated change.

    ``is_resolved`` is ONLY set by Phase 4 when externally-supplied recovery
    telemetry validates the change, so it is the sole path to ``Applied``.
    A validated remediation path that was not executed is ``Pending On-Call
    Action``; nothing actionable at all is ``Not Applied``.
    """
    if report.verification.is_resolved:
        return "Applied"
    if report.runbook_references or report.recommended_actions:
        return "Pending On-Call Action"
    return "Not Applied"


def render_markdown_report(report: IncidentReport) -> str:
    """Render ``report`` into the canonical Phase 5 Markdown structure.

    Population rules: only render already-validated state (Phases 2-4); never
    invent or reinterpret the RCA; missing data is called out explicitly;
    remediation is never claimed as applied without execution+validation
    evidence.
    """
    return "\n\n".join(
        [
            "## Incident Summary",
            _render_overview(report),
            _render_environment(report),
            _render_impacted_services(report),
            _render_impact_assessment(report),
            _render_investigation_findings(report),
            _render_root_cause(report.root_cause),
            _render_recommended_remediation(report),
            _render_investigation_status(report),
            _IMPORTANT_NOTE,
        ]
    ) + "\n"


def _observed_findings(evidence: EvidenceCollection) -> list[str]:
    """Highest-priority observed evidence findings, traceable to evidence ids."""
    observed = [e for e in evidence.items if e.provenance.value == "observed"]
    observed = sorted(observed, key=lambda e: e.severity.lower())
    return [
        f"{e.finding} (source: {e.source}, severity: {e.severity}, "
        f"provenance: {e.provenance.value}, `{e.evidence_id}`)"
        for e in observed[:3]
    ]


def _render_overview(report: IncidentReport) -> str:
    title = report.incident_title or report.incident_id
    description = report.incident_description
    classification = report.classification
    services = ", ".join(classification.affected_services) or "(not established)"
    observed = _observed_findings(report.evidence)
    observed_text = (
        "; ".join(observed)
        if observed
        else "None independently observed -- no telemetry-backed finding was established."
    )
    return (
        "### Incident Overview\n\n"
        f"**Incident:** {report.incident_id}.\n\n"
        f"**Affected service(s):** {services}.\n\n"
        f"**Triggering condition:** {classification.reasoning or '(not established)'}.\n\n"
        f"**Reported trigger (from the source system):** {description or '(none supplied)'}.\n\n"
        f"**Independently observed via telemetry:** {observed_text}.\n\n"
        f"**Summary:** {title} -- the investigation above could not be taken further "
        f"without external recovery/remediation evidence (this pipeline is "
        f"investigate-and-recommend only)."
    )


def _render_environment(report: IncidentReport) -> str:
    env = report.environment or "Unknown (not reported by the source system)"
    return f"### Environment\n\n- **Environment:** `{env}`"


def _render_impacted_services(report: IncidentReport) -> str:
    classification = report.classification
    services = list(classification.affected_services) or ["Unknown / not established"]
    rows = []
    for service in services:
        severity = classification.priority.value
        mentions = [e.finding for e in report.evidence.items if service in e.finding]
        impact = (
            "; ".join(mentions[:2])
            if mentions
            else "Reported in the incident description; no independent telemetry observed."
        )
        rows.append(f"| `{service}` | {severity} | {impact} |")
    header = "### Impacted Services\n\n| Service | Severity / Role | Impact |\n| --- | --- | --- |"
    return header + "\n" + "\n".join(rows)


def _render_impact_assessment(report: IncidentReport) -> str:
    observed = _observed_findings(report.evidence)
    if not observed:
        return (
            "### Impact Assessment\n\n"
            "Impact could not be independently established from available telemetry; "
            "no monitored/logged error behavior, delay, or freshness signal was observed."
        )
    impact = "\n".join(f"- {o}" for o in observed)
    return (
        "### Impact Assessment\n\n"
        f"The following impact was observed in monitored/logged telemetry:\n{impact}"
    )


def _render_investigation_findings(report: IncidentReport) -> str:
    findings: list[str] = []
    for i, item in enumerate(report.evidence.items, start=1):
        findings.append(
            f"{i}. **{item.source}** ({item.severity}, *{item.provenance.value}*): "
            f"{item.finding} <sub>`{item.evidence_id}`</sub>"
        )
    for checkpoint in report.root_cause.claim_validation:
        if not checkpoint.supported:
            findings.append(
                f"- Claim not independently verified ({checkpoint.category.value}): "
                f"`{checkpoint.claim}` -- {checkpoint.qualifier or 'unable to verify from observed telemetry'}"
            )
    if not findings:
        findings.append("_(no evidence collected -- see Impact Assessment)_")
    return "### Investigation Findings\n\n" + "\n".join(findings)


def _render_root_cause(root_cause: RootCauseAnalysis) -> str:
    determination = root_cause_determination(root_cause)
    primary = (
        f"{root_cause.primary_cause.description} "
        f"(confidence {root_cause.confidence_score:.2f}, "
        f"{root_cause.primary_cause.provenance.value})"
    )
    if root_cause.contributing_factors:
        contributing = "\n".join(
            f"- {h.description} (confidence {h.confidence:.2f}, {h.provenance.value})"
            for h in root_cause.contributing_factors
            if h.label != HypothesisLabel.UNLIKELY
        ) or "None identified"
    else:
        contributing = "None identified"
    return (
        "### Root Cause Analysis\n\n"
        f"**Root Cause:** {determination}\n\n"
        f"**Primary cause:** {primary}\n\n"
        f"**Contributing Factors:**\n{contributing}"
    )


def _render_recommended_remediation(report: IncidentReport) -> str:
    runbook_refs = report.runbook_references
    runbook_status = (
        "Applicable runbook found" if runbook_refs else "No applicable runbook found"
    )
    parts = [
        "### Recommended Remediation",
        f"**Runbook Status:** {runbook_status}",
    ]
    if runbook_refs:
        parts.append("**When an Applicable Runbook Is Available:**")
        steps = "\n".join(
            f"{i}. {ref.title} -- [{ref.url}]({ref.url})"
            for i, ref in enumerate(runbook_refs, start=1)
        )
        parts.append(steps)
    else:
        parts.append(f"**When No Applicable Runbook Is Available:**\n\n> {_NO_RUNBOOK_NOTE}")
    if report.recommended_actions:
        action_lines = "\n".join(f"- [ ] {a}" for a in report.recommended_actions)
        parts.append(f"**Recommended next actions (analysis only, not yet executed):**\n{action_lines}")
    return "\n\n".join(parts)


def _render_investigation_status(report: IncidentReport) -> str:
    # The analysis workflow that produced this report has run to completion.
    # That NEVER implies the incident is resolved (rule 6).
    rca_state = root_cause_state_short(report.root_cause)
    remediation = remediation_status(report)
    lines = [
        "### Investigation Status",
        "- **Investigation:** Completed",
        f"- **Root-Cause Analysis:** {rca_state}",
        f"- **Remediation:** {remediation}",
    ]
    if report.verification.needs_reinvestigation:
        lines.append(
            "- **Reinvestigation:** Requested during the bounded loop; no conclusive "
            "outcome was reached on the final pass."
        )
    return "\n".join(lines)


def _evidence_summary(evidence: list) -> str:
    """One-line deterministic summary of the collected evidence."""
    if not evidence:
        return "No evidence item(s) collected"
    sources = sorted({item.source for item in evidence})
    return f"{len(evidence)} evidence item(s) collected from {sources}"


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
    evidence = EvidenceCollection(
        items=evidence_items,
        summary=_evidence_summary(evidence_items),
    )

    root_cause = generate_root_cause_analysis(
        incident, classification, evidence, hypotheses, model=deps.get("rca_model")
    )

    # Phase 3: deterministic claim validation (never an LLM-second-opinion).
    # Unsupported claims are downgraded (confidence + wording) and the RCA
    # confidence is capped by the shared ceiling before nothing is reported.
    findings = validate_hypotheses(incident, evidence_items, hypotheses)
    root_cause = finalize_root_cause(root_cause, findings, hypotheses)
    if findings:
        logger.info(
            "claim validation flagged incident=%s findings=%d",
            state.get("incident_id"),
            len(findings),
        )
    runbook_name = state.get("runbook_name")
    runbook_solution = state.get("runbook_solution")
    runbook_references: list[RunbookReference] = []
    if runbook_name and runbook_solution:
        runbook_references = [
            RunbookReference(runbook_id=runbook_name, title=runbook_name, url=f"runbooks/{runbook_name}")
        ]

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
        runbook_references=runbook_references,
        incident_title=incident.title,
        incident_description=incident.description,
        environment=incident.environment.value,
    )
    if runbook_name and runbook_solution:
        expected_outcome = {
            "expectation": f"Incident resolved by addressing '{runbook_name}'.",
            "action": (
                f"A matching runbook was found for \"{runbook_name}\". "
                f"The recommended resolution from the runbook is: {runbook_solution}"
            ),
        }
    else:
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
        "claim_validation": findings,
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
