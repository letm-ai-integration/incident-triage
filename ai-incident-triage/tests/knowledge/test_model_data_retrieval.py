"""Grounding proofs: RAG retrieval must return real ``model-data`` content.

These tests hit the actual FAISS collections on disk (built by
``scripts/ingest_model_data.py``). They are deliberately specific -- an
incident-specific query must surface chunks that originate from a named
mock-data file and mention the scenario's own vocabulary. A pass here proves
the Log/Kubernetes agents *can* retrieve synchronized mock evidence; the
agent-level tests further down prove they actually receive it.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from app.agents.investigation.log_analysis.agent import analyze_logs_with_fallback
from app.domain.enums.environment import Environment
from app.domain.models.incident import Incident
from app.knowledge.retriever import retrieve


def _incident(service: str, description: str, title: str = "") -> Incident:
    return Incident(
        incident_id="INC-RAG-GROUND",
        title=title or f"{service} degradation",
        description=description,
        source="test",
        service=service,
        environment=Environment.PRODUCTION,
        timestamp=datetime(2026, 8, 6, 10, 20, tzinfo=UTC),
        raw_logs=[],
    )


# ---------------------------------------------------------------------------
# Log RAG retrieval returns db / application mock log chunks
# ---------------------------------------------------------------------------


def test_log_retrieval_returns_checkout_db_pool_chunks():
    chunks = retrieve(
        collection="logs",
        query_text=(
            "checkout-service database connection pool HikariPool exhausted "
            "SQLTransientConnectionException timed out"
        ),
        k=5,
    )
    assert chunks, "logs collection returned nothing"
    top_services = [c.metadata.get("service") for c in chunks]
    assert "checkout-service" in top_services, (
        f"no checkout-service chunk retrieved, got {top_services}"
    )
    target = next(c for c in chunks if c.metadata.get("service") == "checkout-service")
    # The chunk text comes verbatim from model-data log lines, not invented.
    assert "HikariPool" in target.text
    assert target.metadata.get("source_file") in {
        "incident_telemetry_logs.txt",
        "db_logs.txt",
    }


def test_log_retrieval_scopes_by_service():
    """A query anchored to one service must not float to unrelated services."""
    chunks = retrieve(
        collection="logs",
        query_text="inventory-service ClassCastException readiness probe failed",
        k=3,
    )
    assert chunks
    assert any(
        c.metadata.get("service") == "inventory-service" and "ClassCastException" in c.text
        for c in chunks
    ), "inventory-service evidence not retrievable"


@pytest.mark.parametrize("collection", ["logs", "k8s", "metrics", "events", "runbooks"])
def test_all_collections_are_ingested(collection: str):
    from app.knowledge.vector_store import VectorStoreCollectionMissing

    try:
        chunks = retrieve(collection=collection, query_text="pod restart latency error", k=1)
    except VectorStoreCollectionMissing as exc:  # pragma: no cover - committed store
        pytest.fail(f"collection '{collection}' not ingested: {exc}")
    assert isinstance(chunks, list)


# ---------------------------------------------------------------------------
# Kubernetes RAG retrieval returns model-data pod-event chunks
# ---------------------------------------------------------------------------


def test_k8s_retrieval_finds_imagepullbackoff_pod_events():
    chunks = retrieve(
        collection="k8s",
        query_text=(
            "payments-worker pods stuck ImagePullBackOff after deploy "
            "image tag not found container registry rollout"
        ),
        k=5,
    )
    assert chunks, "k8s collection returned nothing"
    pull_hits = [
        c
        for c in chunks
        if c.metadata.get("source_file") == "k8s_logs.json"
        and "ImagePullBackOff" in c.text
    ]
    assert pull_hits, "ImagePullBackOff evidence from model-data/k8s_logs.json not retrieved"


# ---------------------------------------------------------------------------
# Runbook RAG collection holds the named runbooks
# ---------------------------------------------------------------------------


def test_runbook_collection_contains_named_runbooks():
    chunks = retrieve(
        collection="runbooks",
        query_text=(
            "Database Connection Failure Solution recommended resolution "
            "restart rollback pool exhaustion"
        ),
        k=6,
    )
    named = [
        c for c in chunks
        if c.metadata.get("source_file") == "runbooks/database-connection-failure.md"
    ]
    assert named, "named runbook file not present in runbooks collection"
    joined = "".join(c.text for c in named)
    assert "Solution" in joined or "resolution" in joined.lower()


# ---------------------------------------------------------------------------
# Agent level: the LogAnalysisAgent receives and uses the retrieved context
# ---------------------------------------------------------------------------


async def _log_agent_result():
    return await analyze_logs_with_fallback(_incident(
        "checkout-service",
        "checkouts failing while waiting on database connection pool 'HikariPool-1'",
        "Database connection failure on checkout-service",
    ), None, None)


def test_log_agent_fallback_reports_model_data_provenance():
    result = asyncio.run(_log_agent_result())

    raw = result.evidence[0].raw_data
    assert raw.get("retrieved_documents", 0) >= 1, "log agent retrieved no documents"
    assert "checkout-service" in (raw.get("retrieved_services") or [])
    assert result.evidence[0].finding, "log agent produced an empty finding"
