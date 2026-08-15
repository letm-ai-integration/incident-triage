"""Tests for the retriever, with vector-store calls mocked."""
import pytest

from app.knowledge import retriever
from app.knowledge.retriever import RetrievedChunk, retrieve
from app.knowledge.vector_store import VectorStoreCollectionMissing


def test_retrieve_raises_collection_missing(monkeypatch):
    def fake_query(collection_name, text, k=3, where=None):
        raise VectorStoreCollectionMissing("missing")

    monkeypatch.setattr(retriever, "query", fake_query)
    with pytest.raises(VectorStoreCollectionMissing, match="missing"):
        retrieve("not-ingested", "any query")


def test_retrieve_returns_ranked_chunks(monkeypatch):
    def fake_query(collection_name, text, k=3, where=None):
        return {
            "ids": [["a", "b"]],
            "documents": [["doc one", "doc two"]],
            "metadatas": [[{"title": "One"}, {"title": "Two"}]],
            "distances": [[0.8, 0.55]],
        }

    monkeypatch.setattr(retriever, "query", fake_query)
    chunks = retrieve("runbooks", "some query", k=2)
    assert len(chunks) == 2
    assert isinstance(chunks[0], RetrievedChunk)
    assert chunks[0].text == "doc one"
    assert chunks[0].metadata == {"title": "One"}
    assert chunks[0].score == 0.8  # higher = more relevant, preserved in order
    assert chunks[0].score > chunks[1].score


def test_retrieve_empty_result(monkeypatch):
    monkeypatch.setattr(
        retriever,
        "query",
        lambda *a, **k: {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]},
    )
    assert retrieve("runbooks", "anything", k=3) == []


def test_bad_query_metadata_shape_is_tolerated(monkeypatch):
    # Real FAISS returns None metadatas when none were stored; guard against it.
    monkeypatch.setattr(
        retriever,
        "query",
        lambda *a, **k: {
            "ids": [["a"]],
            "documents": [["doc"]],
            "metadatas": [None],
            "distances": [[0.9]],
        },
    )
    chunks = retrieve("runbooks", "q")
    assert chunks[0].metadata == {}