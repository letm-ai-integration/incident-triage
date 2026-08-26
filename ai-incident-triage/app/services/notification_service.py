"""Graph-node adapter for ``deps["notification_service"]``.

Wraps the real notification agent (app/agents/notification/agent.py), which
drafts the email via LLM and delivers it through the Resend adapter.

Delivery semantics for a POC without e-mail configuration: when
``RESEND_API_KEY`` is not set, delivery is *simulated* -- the agent still runs,
but ``send_email`` is skipped and the result reports success with
``message_id=None``. This keeps UI/CLI runs completable offline; configure the
key to get real deliveries (the adapter then behaves identically).
"""
from __future__ import annotations

import logging

from typing import Any

from app.agents.notification.agent import run_notification_agent
from app.config import get_settings
from app.domain.enums.status import NotificationStatus

logger = logging.getLogger(__name__)


def notification_service(state: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    report = state.get("incident_report")
    if report is None:
        # Auto-resolve path: no report was produced, nothing to notify about.
        logger.warning("[notification_service] no incident_report in state -- skipping real notification (simulated)")
        return {"notification_status": NotificationStatus.NOTIFIED}

    if not get_settings().resend_api_key:
        logger.warning("[notification_service] RESEND_API_KEY not configured -- simulating delivery")
        return {
            "notification_status": NotificationStatus.NOTIFIED,
            "notification_detail": "simulated delivery (RESEND_API_KEY not configured)",
        }

    model = deps.get("notification_model")
    logger.info("[notification_service] running notification agent for incident=%s", report.incident_id)
    result = run_notification_agent(report, model=model)
    update: dict[str, Any] = {
        "notification_status": (
            NotificationStatus.NOTIFIED if result.success else NotificationStatus.FAILED
        )
    }
    if result.success:
        logger.info(
            "[notification_service] email delivered to=%s message_id=%s",
            result.recipient,
            result.message_id,
        )
    else:
        logger.error("[notification_service] email delivery failed: %s", result.error)
        update["errors"] = state.get("errors", []) + [
            f"notification failed: {result.error}"
        ]
    return update
