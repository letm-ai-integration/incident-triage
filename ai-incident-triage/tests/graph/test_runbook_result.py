"""Runbook-aware final-result propagation (name-keyed lookup -> RCA output).

Runs the REAL triage graph over the committed vector store with deterministic
fallbacks (no LLM/network), proving:

* an incident whose name matches a ``runbooks/*.md`` file gets the runbook's
  Solution cited verbatim in the final ``expected_outcome`` action;
* an incident without any runbook follows the normal flow with **no** runbook
  claim anywhere in the final result.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.graph.workflow import triage_graph

INCIDENTS = Path(__file__).resolve().parents[2] / "data" / "incidents"
RECURSION_LIMIT = 50


def _deps() -> dict:
    from app.services.investigation_service import investigation_service
    from app.services.notification_service import notification_service

    return {
        "auto_approve": True,
        "investigation_service": investigation_service,
        "notification_service": notification_service,
    }


def _run(raw_input: dict) -> dict:
    return triage_graph.invoke(
        {"raw_input": raw_input},
        config={"configurable": {"deps": _deps()}, "recursion_limit": RECURSION_LIMIT},
    )


def _load(name: str) -> dict:
    return json.loads((INCIDENTS / name).read_text(encoding="utf-8"))


def test_runbook_backed_incident_cites_runbook_in_final_result():
    """INC-006 matches runbooks/database-connection-failure.md by name."""
    result = _run(_load("database-connection-failure.json"))

    assert result["runbook_name"] == "Database Connection Failure"
    assert result["runbook_solution"], "solution not extracted from the runbook"

    outcome = result["expected_outcome"]
    assert outcome["action"].startswith("A matching runbook was found")
    assert f'"{result["runbook_name"]}"' in outcome["action"]

    refs = result["incident_report"].runbook_references
    assert [r.title for r in refs] == ["Database Connection Failure"]


def test_no_runbook_incident_follows_normal_flow():
    """memory-oom has no runbook file -> normal analysis, zero runbook claims."""
    result = _run(_load("memory-oom.json"))

    assert not result.get("runbook_name")
    assert not result.get("runbook_solution")
    assert result["incident_report"].runbook_references == []
    assert not str(result["expected_outcome"]["action"]).startswith(
        "A matching runbook was found"
    )
