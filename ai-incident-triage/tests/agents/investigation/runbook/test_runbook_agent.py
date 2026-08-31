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

# ---------------------------------------------------------------------------
# Name-based runbook resolution against the real on-disk ``runbooks/`` files
# ---------------------------------------------------------------------------


def test_resolver_matches_runbook_by_incident_name():
    from app.agents.investigation.runbook.resolver import resolve_by_name

    doc = resolve_by_name("Database Connection Failure on checkout-db", "pools exhausted")
    assert doc is not None, "no runbook resolved by incident name"
    assert doc.name == "Database Connection Failure"
    assert "runbooks/" in doc.file
    assert doc.solution.strip(), "matched runbook has no usable Solution section"


def test_resolver_ignores_unrelated_incident_names():
    from app.agents.investigation.runbook.resolver import resolve_by_name

    assert (
        resolve_by_name("Graviton scheduler queue stalled", "batch queue drain stuck")
        is None
    )


def test_named_match_returns_verbatim_solution_and_resolution():
    result = run_runbook_agent(
        {
            "title": "Database Connection Failure on checkout-db",
            "description": "connection pool exhausted, checkouts failing",
            "raw_logs": ["SQLTransientConnectionException"],
        },
        _classification(),
    )
    assert result.status == RunbookStatus.MATCHED
    assert result.runbook_name == "Database Connection Failure"
    assert result.solution.strip()
    assert result.resolution.startswith(
        'A matching runbook was found for "Database Connection Failure"'
    )
    assert "recommended resolution from the runbook" in result.resolution


def test_semantic_match_without_name_hit_does_not_claim_a_solution(monkeypatch):
    """FAISS may surface *another* incident's runbook as a candidate. Without a
    name-based match the agent must recognise the candidate but never present
    that foreign runbook's solution as this incident's resolution."""
    from app.knowledge.retriever import RetrievedChunk

    def fake_retrieve(**kwargs):
        return [
            RetrievedChunk(
                text="## High API Latency\n\n**Solution:**\n- Scale out replicas.",
                metadata={"source_file": "runbooks/high-api-latency.md",
                          "title": "High API Latency"},
                score=0.9,
            )
        ]

    monkeypatch.setattr(agent_module, "retrieve", fake_retrieve)
    result = run_runbook_agent(
        {"title": "Graviton scheduler queue stalled",
         "description": "batch scheduling threads stopped draining the job queue",
         "raw_logs": []},
        _classification(),
    )
    # The semantic candidate is acknowledged...
    assert result.matched_title == "High API Latency"
    # ...but it must NOT be treated as a solution-backed runbook match.
    assert not result.solution
    assert not result.runbook_name
    assert not result.resolution
