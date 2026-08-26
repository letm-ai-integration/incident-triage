"""CLI entry point for the incident-triage pipeline.

This is a thin shell over the LangGraph workflow: it loads an incident JSON
file, invokes ``app.graph.workflow.triage_graph`` as the single orchestration
entry point, and prints the result. No triage logic lives here.

Usage:

    python -m app.main data/incidents/database_timeout.json --auto-approve

LLM-backed classification/RCA are opt-in via ``--use-llm`` and require a
provider API key in ``.env``; without it the deterministic rule-based
fallbacks run, so the CLI is fully offline-safe by default.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import typer

from app.graph.workflow import triage_graph
from app.services.classification_service import classification_service
from app.services.investigation_service import investigation_service
from app.services.notification_service import notification_service
from app.services.rca_report_service import rca_report_service

app = typer.Typer(
    add_completion=False,
    help="Run an incident JSON file through the triage LangGraph pipeline.",
)

RECURSION_LIMIT = 50  # safety net on top of MAX_INVESTIGATION_RETRIES


def _load_incident(path: Path) -> dict[str, Any]:
    if not path.exists():
        typer.echo(f"error: file not found: {path}", err=True)
        raise typer.Exit(code=1)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"error: invalid JSON in {path}: {exc}", err=True)
        raise typer.Exit(code=1)
    if not isinstance(raw, dict):
        typer.echo(f"error: invalid JSON in {path}: expected an object", err=True)
        raise typer.Exit(code=1)
    if not raw.get("title") or not raw.get("service"):
        typer.echo(
            "error: incident JSON must contain non-empty 'title' and 'service'",
            err=True,
        )
        raise typer.Exit(code=1)
    return raw


@app.command()
def triage(
    incident_file: Path = typer.Argument(..., help="Path to an incident JSON file."),  # noqa: B008
    auto_approve: bool = typer.Option(
        True, "--auto-approve/--require-approval",
        help="Auto-approve P1/P2 or low-confidence incidents without human sign-off.",
    ),
    use_llm: bool = typer.Option(
        False, "--use-llm",
        help="Use LLM-backed classification/RCA agents (requires a provider API key).",
    ),
) -> None:
    """Triage ``incident_file`` through the graph and print the result."""
    from app.config import get_settings

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    raw_input = _load_incident(incident_file)

    deps: dict[str, Any] = {
        "auto_approve": auto_approve,
        "investigation_service": investigation_service,
        "notification_service": notification_service,
    }
    if use_llm and get_settings().active_llm_config().get("api_key"):
        deps["classification_service"] = classification_service
        deps["rca_report_service"] = rca_report_service

    try:
        result: dict[str, Any] = triage_graph.invoke(
            {"raw_input": raw_input},
            config={"configurable": {"deps": deps}, "recursion_limit": RECURSION_LIMIT},
        )
    except Exception as exc:  # noqa: BLE001 -- CLI boundary: short message, exit 1
        typer.echo(f"error: triage failed: {exc}", err=True)
        raise typer.Exit(code=1)

    incident = result.get("incident")
    classification = result.get("classification")
    approval = result.get("approval")

    typer.echo("Triage Result")
    typer.echo("=" * 60)
    typer.echo(f"Incident file : {incident_file}")
    if incident is not None:
        typer.echo(f"Incident      : {incident.title} ({incident.incident_id})")
        typer.echo(f"Service       : {incident.service} [{incident.environment.value}]")
    if classification is not None:
        typer.echo(
            f"Classification: {classification.incident_type.value} / "
            f"{classification.priority.value} "
            f"(confidence {classification.confidence:.0%})"
        )
    if approval is not None:
        typer.echo(f"Approval      : {'approved' if approval.approved else 'rejected'}"
                   f" by {approval.reviewer}")

    resolved = result.get("is_resolved")
    status = result.get("investigation_status")
    typer.echo(f"Resolution    : {'resolved' if resolved else 'unresolved'} ({status})")

    notification_status = result.get("notification_status")
    if notification_status is not None and notification_status.value == "NOTIFIED":
        detail = result.get("notification_detail")
        suffix = f" ({detail})" if detail else ""
        typer.echo(f"Notified stakeholders{suffix}")
    else:
        typer.echo(f"Notification  : {notification_status}")

    if result.get("errors"):
        typer.echo("Errors:")
        for error in result["errors"]:
            typer.echo(f"  - {error}")


if __name__ == "__main__":
    app()
