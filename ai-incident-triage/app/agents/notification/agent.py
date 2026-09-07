"""
Notification agent: composes and sends an email summarizing a resolved
incident's RCA report to the current on-call/support developer.

Recipient resolution is a deterministic mock lookup (``tools/mock/oncall.py``),
not an LLM decision; the LLM only drafts the email text from the report's actual
fields; delivery happens via the thin Resend adapter (``tools/adapters``).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.agents.notification.parser import (
    NotificationEmail,
    parse_notification_response,
)
from app.agents.notification.prompt import SYSTEM_PROMPT, build_user_prompt
from app.domain.models.report import IncidentReport
from app.guardrails.safety_guard import check_content_safety
from app.guardrails.sanitize import sanitize_html_email_body
from app.llm.client import create_structured_agent
from app.logging_utils import agent_entry, agent_error, agent_exit, agent_output
from app.tools.adapters.resend_email import EmailSendError, send_email
from app.tools.mock.oncall import get_current_oncall

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationResult:
    success: bool
    recipient: str | None = None
    message_id: str | None = None
    error: str | None = None


def _draft_email_llm(rca_report: IncidentReport, contact, model: str | None) -> NotificationEmail:
    """Draft the notification email via the LLM structured agent."""
    agent = create_structured_agent(
        system_prompt=SYSTEM_PROMPT,
        output_schema=NotificationEmail,
        model=model,
    )
    response = agent.invoke(
        {
            "messages": [
                {"role": "user", "content": build_user_prompt(rca_report, contact)}
            ]
        }
    )
    return parse_notification_response(response)


def _draft_email_template(rca_report: IncidentReport) -> NotificationEmail:
    """Deterministic fallback draft built from the report's own fields.

    Renders the full Phase 5 canonical template (all nine sections, in order)
    from already-validated report fields only -- environment and priority come
    from the incident's own values, never invented. This pipeline only
    investigates and recommends, so the email never claims a fix was applied
    unless the report's verification says recovery was validated.
    """
    subject = (
        f"[{rca_report.classification.priority.value}] "
        f"{rca_report.incident_id} - RCA report"
    )
    if not rca_report.verification.is_resolved:
        subject += " (remediation pending)"
    classification = rca_report.classification
    root_cause = rca_report.root_cause
    from app.domain.models.hypothesis import HypothesisLabel
    from app.services.rca_report_service import (
        _observed_findings,
        remediation_status,
        root_cause_determination,
        root_cause_state_short,
    )

    # --- Incident Overview -------------------------------------------------
    services = ", ".join(classification.affected_services) or "(not established)"
    observed = _observed_findings(rca_report.evidence)
    observed_text = (
        "; ".join(observed)
        if observed
        else "None independently observed -- no telemetry-backed finding was established."
    )
    overview = (
        f"<p><b>Incident:</b> {rca_report.incident_id}.</p>"
        f"<p><b>Affected service(s):</b> {services}.</p>"
        "<p><b>Triggering condition:</b> "
        f"{classification.reasoning or '(not established)'}.</p>"
        "<p><b>Reported trigger (from the source system):</b> "
        f"{rca_report.incident_description or '(none supplied)'}.</p>"
        f"<p><b>Independently observed via telemetry:</b> {observed_text}.</p>"
        "<p><b>Summary:</b> "
        f"{rca_report.incident_title or rca_report.incident_id} -- the "
        "investigation above could not be taken further without external "
        "recovery/remediation evidence (this pipeline is investigate-and-recommend only).</p>"
    )

    # --- Environment (incident's own value; the template uses lowercase tokens) ---
    environment = (rca_report.environment or "").strip().lower() or "not reported by the source system"

    # --- Impacted Services (severity = the incident's actual P1-P4 priority) ---
    service_rows = list(classification.affected_services) or ["Unknown / not established"]
    rows = []
    for service in service_rows:
        mentions = [e.finding for e in rca_report.evidence.items if service in e.finding]
        impact = (
            "; ".join(mentions[:2])
            if mentions
            else "Reported in the incident description; no independent telemetry observed."
        )
        rows.append(
            f"<tr><td>{service}</td><td>{classification.priority.value}</td><td>{impact}</td></tr>"
        )
    impacted_services = (
        "<table><thead><tr><th>Service</th><th>Severity / Role</th><th>Impact</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )

    # --- Impact Assessment (only what was actually observed) ---------------
    if observed:
        impact_assessment = (
            "<p>The following impact was observed in monitored/logged telemetry:</p>"
            f"<ul>{''.join(f'<li>{o}</li>' for o in observed)}</ul>"
        )
    else:
        impact_assessment = (
            "<p>Impact could not be independently established from available "
            "telemetry; no monitored/logged error behavior, delay, or "
            "freshness signal was observed.</p>"
        )

    # --- Investigation Findings (every bullet traces to an evidence item) ---
    finding_items = []
    for item in rca_report.evidence.items:
        finding_items.append(
            f"<li><b>{item.source}</b> ({item.severity}, "
            f"<i>{item.provenance.value}</i>): {item.finding} "
            f"(evidence: <b>{item.evidence_id}</b>)</li>"
        )
    for checkpoint in root_cause.claim_validation:
        if not checkpoint.supported:
            finding_items.append(
                "<li>Claim not independently verified "
                f"({checkpoint.category.value}): {checkpoint.claim} -- "
                f"{checkpoint.qualifier or 'unable to verify from observed telemetry'}</li>"
            )
    if not finding_items:
        finding_items.append("<li>(no evidence collected -- see Impact Assessment)</li>")
    investigation_findings = f"<ol>{''.join(finding_items)}</ol>"

    # --- Root Cause Analysis (exact state + contributing factors only) -----
    factor_items = [
        f"<li>{h.description}</li>"
        for h in root_cause.contributing_factors
        if h.label != HypothesisLabel.UNLIKELY
    ]
    contributing = "None identified" if not factor_items else f"<ul>{''.join(factor_items)}</ul>"

    # --- Recommended Remediation (runbook status + runbook/no-runbook arms) ---
    if rca_report.runbook_references:
        steps = rca_report.recommended_actions or [
            f"Follow runbook: {ref.title}" for ref in rca_report.runbook_references
        ]
        remediation_section = (
            "<p><b>Runbook Status:</b> Applicable runbook found</p>"
            "<p><b>When an Applicable Runbook Is Available:</b></p>"
            f"<ol>{''.join(f'<li>{step}</li>' for step in steps)}</ol>"
        )
    else:
        remediation_section = (
            "<p><b>Runbook Status:</b> No applicable runbook found</p>"
            "<p><b>When No Applicable Runbook Is Available:</b></p>"
            "<blockquote><p><b>Runbook remediation unavailable:</b> No "
            "applicable runbook or validated remediation procedure was found. "
            "The investigation has identified the observed symptoms and "
            "available evidence, but a validated remediation path is not "
            "available. <b>On-call engineering action is required to determine, "
            "apply, and validate the appropriate fix.</b></p></blockquote>"
        )
    if rca_report.recommended_actions:
        remediation_section += (
            "<p><b>Recommended next actions (analysis only, not yet executed):</b></p>"
            f"<ul>{''.join(f'<li>{a}</li>' for a in rca_report.recommended_actions)}</ul>"
        )

    # --- Investigation Status (rule 6: completed != resolved) --------------
    investigation_status = (
        "<ul>"
        "<li><b>Investigation:</b> Completed</li>"
        f"<li><b>Root-Cause Analysis:</b> {root_cause_state_short(root_cause)}</li>"
        f"<li><b>Remediation:</b> {remediation_status(rca_report)}</li>"
        "</ul>"
    )
    important_note = (
        "<blockquote><p><b>Important:</b> This investigation is limited to "
        "analysis and recommendation unless explicitly stated otherwise. No "
        "remediation should be considered applied unless there is evidence "
        "the change was actually executed and validated.</p></blockquote>"
    )

    body = (
        "<h2>Incident Summary</h2>"
        "<h3>Incident Overview</h3>"
        f"{overview}"
        "<h3>Environment</h3>"
        f"<p><b>Environment:</b> {environment}</p>"
        "<h3>Impacted Services</h3>"
        f"{impacted_services}"
        "<h3>Impact Assessment</h3>"
        f"{impact_assessment}"
        "<h3>Investigation Findings</h3>"
        f"{investigation_findings}"
        "<h3>Root Cause Analysis</h3>"
        f"<p><b>Root Cause:</b> {root_cause_determination(root_cause)}</p>"
        f"<p><b>Contributing Factors:</b> {contributing}</p>"
        "<h3>Recommended Remediation</h3>"
        f"{remediation_section}"
        "<h3>Investigation Status</h3>"
        f"{investigation_status}"
        f"{important_note}"
    )
    return NotificationEmail(subject=subject, body=body)


def run_notification_agent(
    rca_report: IncidentReport, model: str | None = None
) -> NotificationResult:
    """Compose and send the notification email for ``rca_report``.

    Failures are returned as ``NotificationResult(success=False, error=...)``
    rather than raised -- missing on-call data, an LLM/parse error, or a failed
    send all become an error result, never an uncaught exception. An LLM
    drafting failure falls back to a deterministic template so delivery still
    happens; only a send failure fails the notification.
    """
    agent_entry("NotificationAgent", f"incident={rca_report.incident_id}")
    try:
        contact = get_current_oncall()
        logger.info("[notification.agent] on-call recipient=%s (%s)", contact.email, contact.name)
    except Exception as exc:  # noqa: BLE001
        logger.error("[notification.agent] on-call lookup failed: %s", exc)
        agent_error("NotificationAgent", exc, "on-call lookup failed")
        agent_exit("NotificationAgent")
        return NotificationResult(success=False, error=str(exc))

    try:
        email = _draft_email_llm(rca_report, contact, model)
        logger.info("[notification.agent] email drafted via LLM subject=%r", email.subject)
    except Exception as exc:  # noqa: BLE001 -- LLM unavailable/failure: use template
        logger.warning(
            "[notification.agent] LLM drafting failed (%s: %s); "
            "using deterministic template fallback",
            type(exc).__name__,
            exc,
        )
        agent_error("NotificationAgent", exc, "LLM drafting failed, using template")
        email = _draft_email_template(rca_report)
        logger.info("[notification.agent] email drafted via template subject=%r", email.subject)

    sanitized_body = sanitize_html_email_body(email.body)
    safety_result = check_content_safety("notification", sanitized_body)
    if not safety_result.passed:
        logger.error(
            "[notification.agent] content-safety guardrail blocked email incident=%s findings=%s",
            rca_report.incident_id,
            safety_result.findings,
        )
        return NotificationResult(
            success=False,
            error=f"blocked by content-safety guardrail: {safety_result.findings}",
        )
    email = NotificationEmail(subject=email.subject, body=sanitized_body)

    try:
        message_id = send_email(to=contact.email, subject=email.subject, html_body=email.body)
    except EmailSendError as exc:
        logger.error("[notification.agent] delivery failed: %s", exc)
        agent_error("NotificationAgent", exc, "email delivery failed")
        agent_exit("NotificationAgent")
        return NotificationResult(success=False, error=str(exc))

    agent_output("NotificationAgent", f"delivered to={contact.email} message_id={message_id}")
    agent_exit("NotificationAgent")
    return NotificationResult(success=True, recipient=contact.email, message_id=message_id)