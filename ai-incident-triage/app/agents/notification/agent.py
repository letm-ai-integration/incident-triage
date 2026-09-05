"""
Notification agent: composes and sends an email summarizing a completed
root-cause analysis (investigation findings + recommended runbook fix) to the
current on-call/support developer. This pipeline investigates and diagnoses
only -- it never applies a fix, so the email always frames actions as
recommendations, never as completed remediation.

Recipient resolution is a deterministic mock lookup (``tools/mock/oncall.py``),
not an LLM decision; the LLM only drafts the email text from the report's actual
fields; delivery happens via the thin Resend adapter (``tools/adapters``).
"""
from __future__ import annotations

import html
import logging
from dataclasses import dataclass

from app.agents.notification.parser import (
    NotificationEmail,
    parse_notification_response,
)
from app.agents.notification.prompt import SYSTEM_PROMPT, build_user_prompt
from app.domain.models.hypothesis import HypothesisLabel
from app.domain.models.report import IncidentReport
from app.guardrails.safety_guard import check_content_safety
from app.guardrails.sanitize import sanitize_html_email_body
from app.llm.client import create_structured_agent
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

    Mirrors the LLM prompt's required structure (What happened / Impacted
    services / Steps to be taken as per Runbook for fix / Note) so the
    no-LLM path produces the same investigation-not-remediation framing with
    a full causal-chain narrative, composed only from report data.
    """
    classification = rca_report.classification
    root_cause = rca_report.root_cause
    services = ", ".join(classification.affected_services) or "the affected service(s)"
    contributing = [h.description for h in root_cause.contributing_factors if h.label != HypothesisLabel.UNLIKELY]

    # "What happened" narrative: >= 5 sentences walking the causal chain from
    # trigger -> propagation -> user-visible symptom, using only report fields.
    narrative = [
        (
            f"Incident {rca_report.incident_id} ({classification.incident_type.value}, "
            f"priority {classification.priority.value}) was raised against {services}."
        ),
        f"Investigation identified the trigger: {root_cause.primary_cause.description}.",
    ]
    if contributing:
        narrative.append(
            "The following contributing factors fed into the failure: "
            + "; ".join(contributing)
            + "."
        )
    if rca_report.evidence.summary:
        narrative.append(f"Corroborating evidence collected during investigation: {rca_report.evidence.summary}.")
    if root_cause.timeline:
        steps = "; ".join(f"{e.timestamp} {e.description}" for e in root_cause.timeline)
        narrative.append(f"Reconstructed timeline: {steps}.")
    narrative.append(
        "The end-user-visible symptom was degraded behaviour on the affected "
        "service(s) while this condition persisted."
    )
    narrative.append(
        "Root-cause analysis is complete; no remediation has been applied by "
        "this system, and the fix remains pending on-call action."
    )

    runbook_actions = [
        a for a in rca_report.recommended_actions if a.lower().startswith("follow runbook")
    ]
    other_actions = [a for a in rca_report.recommended_actions if a not in runbook_actions]
    recommendations = runbook_actions + other_actions

    subject = (
        f"[{classification.priority.value}] {rca_report.incident_id} - "
        f"RCA complete, remediation recommended"
    )
    if recommendations:
        action_items = "".join(f"<li>{html.escape(action)}</li>" for action in recommendations)
    else:
        action_items = "<li>(none listed)</li>"
    body = (
        f"<h2>Incident {rca_report.incident_id} - RCA Report</h2>"
        "<h3>What happened</h3>"
        + "".join(f"<p>{html.escape(sentence)}</p>" for sentence in narrative)
        + "<h3>Impacted services</h3>"
        f"<p><b>Type:</b> {classification.incident_type.value} · "
        f"<b>Severity:</b> {classification.priority.value} · "
        f"<b>Services:</b> {services}</p>"
        f"<p><b>Root cause (confidence {root_cause.confidence_score:.2f}):</b> "
        f"{html.escape(root_cause.primary_cause.description)}</p>"
        "<h3>Steps to be taken as per Runbook for fix:</h3>"
        "<ul>"
        + action_items
        + "</ul>"
        "<p><b>Note:</b> This system performed investigation and root-cause "
        "analysis only. No fix has been applied; remediation is pending "
        "on-call action per the runbook above.</p>"
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
    try:
        contact = get_current_oncall()
        logger.info("[notification.agent] on-call recipient=%s (%s)", contact.email, contact.name)
    except Exception as exc:  # noqa: BLE001
        logger.error("[notification.agent] on-call lookup failed: %s", exc)
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
        return NotificationResult(success=False, error=str(exc))

    return NotificationResult(success=True, recipient=contact.email, message_id=message_id)