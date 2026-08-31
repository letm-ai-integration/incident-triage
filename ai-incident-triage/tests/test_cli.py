"""CLI tests for the ``ai-incident-triage`` command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from app.main import app

runner = CliRunner()

INCIDENTS = Path(__file__).parent.parent / "data" / "incidents"


def test_auto_approve_database_timeout() -> None:
    result = runner.invoke(
        app,
        [str(INCIDENTS / "database_timeout.json"), "--auto-approve"],
    )
    assert result.exit_code == 0
    assert "Triage Result" in result.stdout
    assert "Database connection pool exhausted" in result.stdout
    assert "approved" in result.stdout
    assert "Notified stakeholders" in result.stdout


def test_auto_approve_unresolved_incident() -> None:
    # unmatched-no-telemetry.json describes a service with zero coverage in
    # model-data, so investigation stays inconclusive and runs CLI reports it
    # as unresolved instead of claiming a RAG-grounded root cause.
    result = runner.invoke(
        app,
        [str(INCIDENTS / "unmatched-no-telemetry.json"), "--auto-approve"],
    )
    assert result.exit_code == 0
    assert "Graviton scheduler queue stalled" in result.stdout
    assert "unresolved" in result.stdout


def test_missing_file_exits_nonzero() -> None:
    result = runner.invoke(
        app,
        ["data/incidents/does_not_exist.json", "--auto-approve"],
    )
    assert result.exit_code == 1
    assert "file not found" in result.stderr


def test_invalid_json_exits_nonzero(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    result = runner.invoke(app, [str(bad), "--auto-approve"])
    assert result.exit_code == 1
    assert "invalid JSON" in result.stderr


def test_missing_title_exits_nonzero(tmp_path: Path) -> None:
    no_title = tmp_path / "no_title.json"
    no_title.write_text("{}", encoding="utf-8")
    result = runner.invoke(app, [str(no_title), "--auto-approve"])
    assert result.exit_code == 1
    assert "'title'" in result.stderr
