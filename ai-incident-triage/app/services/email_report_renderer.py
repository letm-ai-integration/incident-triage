"""Render the fixed-structure incident report / notification HTML.

Single reusable template file: ``app/prompts/templates/incident_report_email.html``
(populated from the validated :class:`~app.domain.models.report.IncidentReport`
only -- never generated ad hoc per incident). The template is a table-based,
inline-CSS document so it renders correctly in the most restrictive corporate
email clients (Outlook) and, being plain valid HTML, can also be embedded in the
Streamlit UI unchanged.

Security: the Jinja2 environment renders with ``autoescape=True``, so every
incident-derived value (descriptions, findings, service names, logs) is
HTML-escaped before it reaches the template -- incident text containing ``<``,
``>``, ``&`` or quotes can never break the structure or inject markup.



The data-binding mirrors the existing structural report-generation logic
(see ``app/agents/notification/agent.py:_draft_email_template``): every one of
the 8 body sections maps the same validated report fields to the same content,
and every field that can be missing at render time resolves to the explicit
human-readable fallback required by the edge-case contract below.

"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2

from app.domain.enums.priority import Priority
from app.domain.models.hypothesis import HypothesisLabel
from app.domain.models.report import IncidentReport
from app.services.rca_report_service import (
    _observed_findings,
    remediation_status,
    root_cause_determination,
    root_cause_state_short,
)

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "prompts" / "templates"
_TEMPLATE_NAME = "incident_report_email.html"

_JP = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

# ---------------------------------------------------------------------------
# Badge palette (email-safe hex).
# Severity: P1 red, P2 orange, P3 amber/yellow, P4 gray;
#   unknown -> neutral gray.
# Root-cause: Confirmed green, Probable amber, inconclusive gray.



# Remediation: Not Applied gray, Pending On-Call Action amber, Applied green.



# ---------------------------------------------------------------------------
_COLOR_P1 = "#d64545"
_COLOR_P2 = "#e8590c"
_COLOR_P3 = "#d29922"
_COLOR_P4 = "#8b949e"
_COLOR_NEUTRAL = "#8b949e"
_COLOR_CONFIRMED = "#2ea043"
_COLOR_AMBER = "#d29922"
_COLOR_GRAY = "#8b949e"

_SEVERITY_COLORS = {
    "P1": _COLOR_P1,
    "P2": _COLOR_P2,
    "P3": _COLOR_P3,
    "P4": _COLOR_P4,
}

_DISCLAIMER = (
    "This investigation is limited to analysis and recommendation unless "
    "explicitly stated otherwise. No remediation should be considered applied "
    "unless there is evidence the change was actually executed and validated."
)


def _severity(priority: Priority | None) -> tuple[str, str]:
    """``(label, color)`` for the header severity badge."""
    if priority is None:
        return "Not specified", _COLOR_NEUTRAL
    label = priority.value
    return label, _SEVERITY_COLORS.get(label, _COLOR_NEUTRAL)


def _root_cause_badge(root_cause: Any) -> tuple[str, str]:
    """``(label, color)`` for the Root Cause Analysis state badge."""
    determination = root_cause_determination(root_cause)
    if determination.startswith("Confirmed"):
        return "Confirmed", _COLOR_CONFIRMED
    if determination.startswith("Probable"):
        return "Probable", _COLOR_AMBER
    return "Root cause could not be conclusively determined", _COLOR_GRAY


def _rca_state_badge(root_cause: Any) -> tuple[str, str]:
    """``(label, color)`` for the Investigation Status Root-Cause row."""
    state = root_cause_state_short(root_cause)  # Confirmed / Probable / Inconclusive
    color = {
        "Confirmed": _COLOR_CONFIRMED,
        "Probable": _COLOR_AMBER,
    }.get(state, _COLOR_GRAY)
    return state, color


def _remediation_state_badge(report: IncidentReport) -> tuple[str, str]:
    """``(label, color)`` for the Investigation Status Remediation row."""
    state = remediation_status(report)  # Not Applied / Applied / Pending On-Call Action
    color = {
        "Applied": _COLOR_CONFIRMED,
        "Pending On-Call Action": _COLOR_AMBER,
    }.get(state, _COLOR_GRAY)
    return state, color


def _format_generated_at(report: IncidentReport) -> str:
    """Small, human-readable timestamp for the header band."""
    return report.created_at.strftime("%Y-%m-%d %H:%M UTC")


def _build_context(report: IncidentReport, run_id: str | None) -> dict[str, Any]:
    """Map the validated report's fields onto the template's fixed structure.




    Every key the template reads is set here, and every field is resolved to a
    concrete value or an explicit fallback -- ``None`` never reaches the markup.


    """
    classification = report.classification
    root_cause = report.root_cause
    severity_label, severity_color = _severity(classification.priority)



    # --- Incident Overview (narrative paragraphs) --------------------------
    services = ", ".join(classification.affected_services) or "(not established)"
    observed = _observed_findings(report.evidence)
    observed_text = (
        "; ".join(observed)
        if observed
        else "None independently observed -- no telemetry-backed finding was established."
    )
    overview_paragraphs = [
        f"Incident: {report.incident_id}.",
        f"Affected service(s): {services}.",
        f"Triggering condition: {classification.reasoning or '(not established)'}.",
        f"Reported trigger (from the source system): {report.incident_description or '(none supplied)'}.",
        f"Independently observed via telemetry: {observed_text}.",
        (
            f"Summary: {report.incident_title or report.incident_id} --the investigation "
            "above could not be taken further without external recovery/remediation evidence "
            "(this pipeline is investigate-and-recommend only)."
        ),
    ]




    # --- Environment --------------------------------------------------------
    raw_env = (report.environment or "").strip()
    environment_label = raw_env.title() if raw_env else "Not specified"




    # --- Impacted Services --------------------------------------------------
    service_names = list(classification.affected_services)
    service_rows = []
    for service in service_names:


        mentions = [e.finding for e in report.evidence.items if service in e.finding]
        impact = (
            "; ".join(mentions[:2])
            if mentions
            else "Reported in the incident description; no independent telemetry observed."
        )
        service_rows.append(
            {
                "service": service,
                "severity": classification.priority.value if classification.priority else "Unknown",
                "impact": impact,
            }
        )



    # --- Impact Assessment --------------------------------------------------
    if observed:
        impact_paragraphs = ["The following impact was observed in monitored/logged telemetry:"]
        impact_items = list(observed)
    else:
        impact_paragraphs = [
            (
                "Impact could not be independently established from available telemetry; "
                "no monitored/logged error behavior, delay, or freshness signal was observed."
            )
        ]
        impact_items = []



    # --- Investigation Findings ---------------------------------------------
    findings: list[str] = []
    for item in report.evidence.items:
        findings.append(
            f"{item.source} ({item.severity}, {item.provenance.value}): "
            f"{item.finding} (evidence: {item.evidence_id})"
        )
    for checkpoint in root_cause.claim_validation:
        if not checkpoint.supported:
            findings.append(
                f"Claim not independently verified ({checkpoint.category.value}): "
                f"{checkpoint.claim} -- {checkpoint.qualifier or 'unable to verify from observed telemetry'}"
            )


# --- Root Cause Analysis ------------------------------------------------
    rc_label, rc_color = _root_cause_badge(root_cause)
    contributing_factors = [
        h.description
        for h in root_cause.contributing_factors
        if h.label != HypothesisLabel.UNLIKELY
    ]




    # --- Recommended Remediation ---------------------------------------------
    if report.runbook_references:
        runbook_status = "Applicable runbook found"
        remediation_steps = report.recommended_actions or [
            f"Follow runbook: {ref.title}" for ref in report.runbook_references
        ]
        no_runbook = False
    else:
        runbook_status = "No applicable runbook found"
        remediation_steps = []
        no_runbook = True




    # --- Investigation Status ------------------------------------------------
    investigation_label = "Completed"
    investigation_color = _COLOR_CONFIRMED
    rca_state, rca_color = _rca_state_badge(root_cause)
    remediation_state, remediation_state_color = _remediation_state_badge(report)


    return {
        # header
        "incident_id": report.incident_id,
        "severity_label": severity_label,
        "severity_color": severity_color,
        "generated_at": _format_generated_at(report),
        # 1
        "overview_paragraphs": overview_paragraphs,
        # 2
        "environment_label": environment_label,
        # 3
        "impacted_services_empty": not service_rows,
        "impacted_services": service_rows,
        # 4
        "impact_assessment_paragraphs": impact_paragraphs,
        "impact_assessment_items": impact_items,
        # 5
        "findings_empty": not findings,
        "findings": findings,
        # 6
        "root_cause_state": rc_label,
        "root_cause_color": rc_color,
        "root_cause_explanation": root_cause.primary_cause.description,
        "contributing_factors": contributing_factors,
        # 7
        "runbook_status": runbook_status,
        "no_runbook": no_runbook,
        "remediation_steps": remediation_steps,
        "remediation_actions": report.recommended_actions,
        # 8
        "investigation_label": investigation_label,
        "investigation_color": investigation_color,
        "rca_state": rca_state,
        "rca_color": rca_color,
        "remediation_state": remediation_state,
        "remediation_state_color": remediation_state_color,
        "disclaimer": _DISCLAIMER,
        # footer
        "run_id": run_id or "Not recorded",
    }


def render_html_email_report(report: IncidentReport, run_id: str | None = None) -> str:
    """Populate the fixed template from ``report`` and render the full HTML.

    ``run_id`` is rendered in the footer band; ``None`` resolves to the
    explicit ``Not recorded`` fallback string, never a raw ``None``.



    """
    template = _JP.get_template(_TEMPLATE_NAME)
    return template.render(**_build_context(report, run_id))