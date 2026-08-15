"""Tests for the RAG-backed runbook agent.

The retriever (and its embedding/FAISS stack) is mocked at the boundary the
agent calls -- no real embedding model or vector store is touched.
"""

from app.agents.investigation.runbook import agent as agent_module
from app.agents.investigation.runbook.agent import (
    MIN_RELEVANCE_SCORE,
    run_runbook_agent,
)
from app.domain.models.classification import ClassificationResult
from app.graph.state import RunbookStatus
from app.knowledge.retriever import RetrievedChunk
from app.knowledge.vector_store import VectorStoreCollectionMissing

ALERT = {
    "title": "HTTP 503 responses exceeding 5% of request volume",
    "description": "Service is returning Service Unavailable for almost all requests",
    "service": "api-gateway",
    "raw_logs": ["503 Service Unavailable", "readiness probe failed"],
}


def _classification() -> ClassificationResult:
    return ClassificationResult(
        incident_type="APPLICATION",
        priority="P2",
        confidence=0.9,
        reasoning="mock",
        agrees_with_rule=True,
    )


def _chunk(text: str = "## High API Failures\n\n**Solution:**\n- Roll back.", score: float = 0.8) -> RetrievedChunk:
    return RetrievedChunk(
        text=text,
        metadata={"source_file": "runbook.md", "title": "High API Failures"},
        score=score,
    )


def test_strong_match_returns_matched(monkeypatch):
    monkeypatch.setattr(agent_module, "retrieve", lambda **kwargs: [_chunk(score=0.85)])
    result = run_runbook_agent(ALERT, _classification())
    assert result.status == RunbookStatus.MATCHED
    assert result.hypothesis is not None
    assert result.matched_title == "High API Failures"
    assert result.hypothesis.description.startswith("## High API Failures")
    assert result.score == 0.85


def test_weak_match_returns_no_match(monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "retrieve",
        lambda **kwargs: [_chunk(score=MIN_RELEVANCE_SCORE - 0.1)],
    )
    result = run_runbook_agent(ALERT, _classification())
    assert result.status == RunbookStatus.NO_MATCH
    assert result.hypothesis is None


def test_empty_results_returns_no_match(monkeypatch):
    monkeypatch.setattr(agent_module, "retrieve", lambda **kwargs: [])
    result = run_runbook_agent(ALERT, _classification())
    assert result.status == RunbookStatus.NO_MATCH


def test_collection_missing_returns_error(monkeypatch):
    def fake_retrieve(**kwargs):
        raise VectorStoreCollectionMissing("runbooks collection missing")

    monkeypatch.setattr(agent_module, "retrieve", fake_retrieve)
    result = run_runbook_agent(ALERT, _classification())
    assert result.status == RunbookStatus.ERROR
    assert "missing" in (result.error or "").lower()


def test_unexpected_error_returns_error(monkeypatch):
    def fake_retrieve(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(agent_module, "retrieve", fake_retrieve)
    result = run_runbook_agent(ALERT, _classification())
    assert result.status == RunbookStatus.ERROR
    assert "Runbook search failed" in (result.error or "")


def test_query_building_uses_classification_and_alert(monkeypatch):
    captured = {}

    def fake_retrieve(collection, query_text, k):
        captured["collection"] = collection
        captured["query_text"] = query_text
        captured["k"] = k
        return [_chunk(score=0.9)]

    monkeypatch.setattr(agent_module, "retrieve", fake_retrieve)
    run_runbook_agent(ALERT, _classification())
    assert captured["collection"] == "runbooks"
    assert captured["k"] == 3
    assert "APPLICATION" in captured["query_text"]
    assert "HTTP 503" in captured["query_text"]
    assert "Service Unavailable" in captured["query_text"]