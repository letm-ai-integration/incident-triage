"""
Thin, collection-agnostic wrapper over a local FAISS vector store.

No file in this module ever references a specific knowledge domain -- the
collection name is always a parameter. Each collection is a directory under
``settings.vector_store_path`` containing:

  index.faiss       -- the FAISS index (inner-product over normalized vectors,
                       i.e. cosine similarity; higher score = more relevant)
  metadata.json     -- sidecar list of {"id", "text", "metadata"} in the same
                       order as the index rows (FAISS itself stores no metadata)

Design mirrors the reference RAG POC (rag-qna-bot-poc): local FAISS, local
sentence-transformers embeddings, embedded persistence on disk, no external
service. Ingestion is manual (scripts/ingest_knowledge.py), and rebuilds the
collection from the merged documents, which gives true upsert semantics --
re-running ingestion is safe.
"""
from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

from app.config import get_settings
from app.knowledge.embeddings import embed_query, embed_texts


class VectorStoreCollectionMissing(Exception):
    """Raised when a collection has never been ingested."""


def _collection_dir(collection_name: str) -> Path:
    settings = get_settings()
    return Path(settings.vector_store_path) / collection_name


def _index_path(collection_name: str) -> Path:
    return _collection_dir(collection_name) / "index.faiss"


def _metadata_path(collection_name: str) -> Path:
    return _collection_dir(collection_name) / "metadata.json"


def collection_exists(name: str) -> bool:
    return _index_path(name).exists() and _metadata_path(name).exists()


def get_or_create_collection(name: str) -> Path:
    """Return the collection directory, creating it on first use."""
    path = _collection_dir(name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_entries(collection_name: str) -> list[dict]:
    with open(_metadata_path(collection_name), encoding="utf-8") as fh:
        return json.load(fh)


def _save_collection(collection_name: str, entries: list[dict], vectors: np.ndarray) -> None:
    get_or_create_collection(collection_name)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors.astype("float32"))
    faiss.write_index(index, str(_index_path(collection_name)))
    with open(_metadata_path(collection_name), "w", encoding="utf-8") as fh:
        json.dump(entries, fh, ensure_ascii=False, indent=2)


def add_documents(collection_name: str, docs: list[str], metadatas: list[dict], ids: list[str]) -> None:
    """Upsert documents into ``collection_name``.

    Re-running with the same ids replaces those entries instead of duplicating
    them. Rebuilds the index on every call -- fine for manual, human-triggered
    ingestion of curated documents.
    """
    if collection_exists(collection_name):
        existing = _load_entries(collection_name)
        merged = {entry["id"]: entry for entry in existing}
    else:
        merged = {}

    for doc, meta, doc_id in zip(docs, metadatas, ids):
        merged[doc_id] = {"id": doc_id, "text": doc, "metadata": meta}

    entries = list(merged.values())
    if not entries:
        return

    vectors = np.array(embed_texts([entry["text"] for entry in entries]), dtype="float32")
    _save_collection(collection_name, entries, vectors)


def query(collection_name: str, text: str, k: int = 3, where: dict | None = None) -> dict:
    """Run a similarity search, returning a Chroma-shaped result dict.

    Raises ``VectorStoreCollectionMissing`` when the collection has never been
    ingested -- callers must handle this distinctly from an empty result.
    """
    if not collection_exists(collection_name):
        raise VectorStoreCollectionMissing(
            f"Collection '{collection_name}' does not exist yet -- "
            "run scripts/ingest_knowledge.py first."
        )

    entries = _load_entries(collection_name)

    if where:
        keep = [
            i
            for i, entry in enumerate(entries)
            if all(entry["metadata"].get(key) == value for key, value in where.items())
        ]
    else:
        keep = list(range(len(entries)))

    docs = [entries[i]["text"] for i in keep]
    metas = [entries[i]["metadata"] for i in keep]
    ids = [entries[i]["id"] for i in keep]

    if not docs or k <= 0:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    index = faiss.read_index(str(_index_path(collection_name)))
    query_vec = np.array([embed_query(text)], dtype="float32")

    # The FAISS index stores the full collection; reconstruct only the rows
    # matching the optional ``where`` filter and score them against the query.
    full_vectors = np.array(
        [index.reconstruct(i) for i in range(index.ntotal)], dtype="float32"
    )
    subset_vecs = full_vectors[keep]

    q = query_vec[0]
    scores = subset_vecs @ q
    order = np.argsort(-scores)[:k]

    return {
        "ids": [[ids[i] for i in order]],
        "documents": [[docs[i] for i in order]],
        "metadatas": [[metas[i] for i in order]],
        "distances": [[float(scores[i]) for i in order]],
    }