from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.services.runbook_learning_service import run_runbook_learning_loop, _append_to_runbook, _create_new_runbook, _slugify_segment, _generate_runbook_filename
from app.services.notification_service import notification_service
from app.domain.enums.priority import Priority
from app.domain.enums.incident_type import IncidentType
from app.domain.models.classification import ClassificationResult
from app.domain.models.incident import Incident
from app.domain.models.root_cause import RootCauseAnalysis
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.verification import VerificationResult
from app.domain.models.report import IncidentReport
from app.domain.enums.environment import Environment
from app.knowledge.retriever import RetrievedChunk
from app.domain.models.evidence import EvidenceCollection


@pytest.fixture
def mock_incident_state():
    incident = Incident(
        incident_id="INC-123",
        title="DB Timeout",
        description="Timeouts to the main DB",
        source="manual-ui",
        service="backend",
        environment=Environment.PRODUCTION,
        timestamp="2026-08-27T10:00:00Z"
    )
    classification = ClassificationResult(
        incident_type=IncidentType.DATABASE,
        priority=Priority.P1,
        confidence=0.9,
        reasoning="DB is overloaded",
        agrees_with_rule=True,
        affected_services=["backend"]
    )
    hypothesis = Hypothesis(
        hypothesis_id="HYP-1",
        description="Exhausted pool",
        confidence=0.9,
        label=HypothesisLabel.LIKELY
    )
    rca = RootCauseAnalysis(
        primary_cause=hypothesis,
        contributing_factors=[],
        confidence_score=0.9
    )
    verification = VerificationResult(
        is_resolved=True,
        resolution_evidence="Logs show no more timeouts.",
        needs_reinvestigation=False
    )
    report = IncidentReport(
        incident_id="INC-123",
        classification=classification,
        evidence=EvidenceCollection(summary="No DB connections available"),
        root_cause=rca,
        recommended_actions=["Increase pool size"],
        verification=verification,
        created_at="2026-08-27T10:00:00Z"
    )
    
    return {
        "incident": incident,
        "classification": classification,
        "root_cause": rca,
        "verification_result": verification,
        "incident_report": report
    }

def test_slugify_segment():
    assert _slugify_segment("Payment-API") == "payment-api"
    assert _slugify_segment("OOMKilled! ") == "oomkilled"
    assert _slugify_segment("some/long/path/with:colons") == "some-long-path-with-colons"
    assert _slugify_segment("  spaces   and  --  hyphens  ") == "spaces-and-hyphens"
    assert _slugify_segment(None) == "unknown"
    assert _slugify_segment("") == "unknown"
    assert _slugify_segment("a" * 50, max_length=10) == "a" * 10


def test_generate_runbook_filename(mock_incident_state, tmp_path):
    # Test normal generation
    file_path = _generate_runbook_filename(
        mock_incident_state["incident"],
        mock_incident_state["classification"],
        tmp_path
    )
    assert file_path.name == "database--backend--production.md"
    
    # Test fallback generation
    mock_incident_state["classification"].incident_type = None
    mock_incident_state["incident"].service = ""
    mock_incident_state["incident"].environment = None
    
    file_path2 = _generate_runbook_filename(
        mock_incident_state["incident"],
        mock_incident_state["classification"],
        tmp_path
    )
    assert file_path2.name == "generic--cluster-wide--unknown-env.md"
    
    # Restore mock for collision
    mock_incident_state["classification"].incident_type = IncidentType.DATABASE
    mock_incident_state["incident"].service = "backend"
    mock_incident_state["incident"].environment = Environment.PRODUCTION
    
    # Test collision handling
    file_path.touch()
    file_path_col1 = _generate_runbook_filename(
        mock_incident_state["incident"],
        mock_incident_state["classification"],
        tmp_path
    )
    assert file_path_col1.name == "database--backend--production-2.md"
    file_path_col1.touch()
    
    file_path_col2 = _generate_runbook_filename(
        mock_incident_state["incident"],
        mock_incident_state["classification"],
        tmp_path
    )
    assert file_path_col2.name == "database--backend--production-3.md"
def test_similarity_threshold_above(mock_incident_state, tmp_path):
    mock_runbook = tmp_path / "test_runbook.md"
    mock_runbook.write_text("# Old Runbook\n")

    with patch("app.services.runbook_learning_service.retrieve") as mock_retrieve, \
         patch("app.services.runbook_learning_service.get_settings") as mock_settings, \
         patch("app.services.runbook_learning_service.ingest_file_into_collection"):
        
        # Mock settings for threshold
        mock_settings.return_value.runbook_update_similarity_threshold = 0.8
        
        # Mock retrieve to return a high score match
        mock_retrieve.return_value = [
            RetrievedChunk(text="foo", metadata={"source_file": str(mock_runbook)}, score=0.9)
        ]

        result = run_runbook_learning_loop(mock_incident_state)
        
        assert result["runbook_learning_attempted"] is True
        assert result["runbook_learning_file_touched"] == str(mock_runbook)
        assert result["runbook_learning_similarity_score"] == 0.9
        
        content = mock_runbook.read_text()
        assert "# Old Runbook\n" in content
        assert "## Observed Incident" in content
        assert "Exhausted pool" in content


def test_similarity_threshold_below(mock_incident_state, tmp_path):
    with patch("app.services.runbook_learning_service.retrieve") as mock_retrieve, \
         patch("app.services.runbook_learning_service.get_settings") as mock_settings, \
         patch("app.services.runbook_learning_service.RUNBOOKS_DIR", tmp_path), \
         patch("app.llm.client.chat_completion") as mock_chat, \
         patch("app.services.runbook_learning_service.ingest_file_into_collection"):
        
        # Mock settings for threshold
        mock_settings.return_value.runbook_update_similarity_threshold = 0.8
        
        # Mock retrieve to return a low score match
        mock_retrieve.return_value = [
            RetrievedChunk(text="foo", metadata={"source_file": "dummy.md"}, score=0.5)
        ]
        
        # Mock LLM response
        mock_msg = MagicMock()
        mock_msg.choices = [MagicMock()]
        mock_msg.choices[0].message.content = "---\ntitle: DB Timeout\n---\n# New Runbook Content"
        mock_chat.return_value = mock_msg

        result = run_runbook_learning_loop(mock_incident_state)
        
        assert result["runbook_learning_attempted"] is True
        assert result["runbook_learning_similarity_score"] == 0.5
        
        new_file = Path(result["runbook_learning_file_touched"])
        assert new_file.exists()
        assert new_file.parent == tmp_path
        assert new_file.name == "database--backend--production.md"
        
        content = new_file.read_text()
        assert "title: DB Timeout" in content


def test_markdown_append_logic(mock_incident_state, tmp_path):
    mock_runbook = tmp_path / "append_test.md"
    mock_runbook.write_text("# Existing Header\n\nSome body text.")
    
    _append_to_runbook(
        str(mock_runbook), 
        "INC-123", 
        mock_incident_state["classification"],
        mock_incident_state["root_cause"],
        mock_incident_state["verification_result"]
    )
    
    content = mock_runbook.read_text()
    assert content.startswith("# Existing Header\n\nSome body text.")
    assert "## Observed Incident" in content
    assert "**Severity:** P1" in content
    assert "**Root Cause:** Exhausted pool" in content


def test_markdown_create_logic(mock_incident_state, tmp_path):
    with patch("app.services.runbook_learning_service.RUNBOOKS_DIR", tmp_path), \
         patch("app.llm.client.chat_completion") as mock_chat:
        
        # Mock LLM response with formatting
        mock_msg = MagicMock()
        mock_msg.choices = [MagicMock()]
        mock_msg.choices[0].message.content = "```markdown\n---\ntitle: test\n---\n# Content\n```"
        mock_chat.return_value = mock_msg
        
        file_path = _create_new_runbook(
            mock_incident_state["incident"],
            mock_incident_state["classification"],
            mock_incident_state["root_cause"],
            mock_incident_state["verification_result"],
            mock_incident_state["incident_report"]
        )
        
        new_file = Path(file_path)
        assert new_file.exists()
        assert new_file.name == "database--backend--production.md"
        content = new_file.read_text()
        # Verify markdown stripping logic worked
        assert content == "---\ntitle: test\n---\n# Content"


def test_failure_isolation_in_notification_service(mock_incident_state):
    # Ensure notification node completes even if learning loop raises an exception
    with patch("app.services.notification_service.get_settings") as mock_settings, \
         patch("app.services.notification_service.run_notification_agent") as mock_notify, \
         patch("app.services.runbook_learning_service.run_runbook_learning_loop") as mock_loop:
        
        # Mock configuration for simulated email delivery to avoid actual Resend call
        mock_settings.return_value.resend_api_key = "dummy"
        
        # Mock the notification agent to succeed
        mock_notify_result = MagicMock()
        mock_notify_result.success = True
        mock_notify_result.recipient = "test@example.com"
        mock_notify_result.message_id = "msg_123"
        mock_notify.return_value = mock_notify_result
        
        # Force the learning loop to fail completely
        mock_loop.side_effect = RuntimeError("Simulated failure in learning loop")
        
        # Run the notification service
        update = notification_service(mock_incident_state, deps={"notification_model": None})
        
        # Even though learning loop failed, notification status should be NOTIFIED
        assert update["notification_status"].value == "NOTIFIED"
        # The unhandled exception shouldn't propagate up and break the node.
