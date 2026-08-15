"""
Public, collection-agnostic retrieval API.

This is the ONLY file agents should import from ``app.knowledge/``.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.knowledge.vector_store import query


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    metadata: dict
    score: float  # cosine similarity; higher = more relevant


def retrieve(collection: str, query_text: str, k: int = 3) -> list[RetrievedChunk]:
    """Retrieve the top-``k`` chunks for ``query_text`` from ``collection``.

    Raises ``VectorStoreCollectionMissing`` if the collection hasn't been
    ingested yet -- callers must handle this distinctly from "no results."
    """
    result = query(collection, query_text, k=k)
    docs = result.get("documents", [[]])[0] or []
    raw_metadatas = result.get("metadatas", [[]])[0]
    metadatas = [meta or {} for meta in raw_metadatas] if raw_metadatas else [{} for _ in docs]
    distances = result.get("distances", [[]])[0] or []
    chunks = [
        RetrievedChunk(text=doc, metadata=meta, score=score)
        for doc, meta, score in zip(docs, metadatas, distances)
    ]
    return chunks