"""
Local embedding function used across all collections.

Mirrors the embedding stack from the reference RAG POC
(rag-qna-bot-poc): a local sentence-transformers model
(``sentence-transformers/all-MiniLM-L6-v2``). Running locally means no API
key and no external service -- embeddings are provider-agnostic (independent
of the LLM provider selected for chat).
"""
from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import get_settings


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    settings = get_settings()
    return SentenceTransformer(settings.embedding_model_name)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts, returning L2-normalized vectors.

    Normalization makes FAISS's inner-product index behave like cosine
    similarity, so higher scores = more relevant.
    """
    model = _load_model()
    return model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).tolist()


def embed_query(text: str) -> list[float]:
    """Embed a single query string, normalized exactly like ``embed_texts``."""
    return embed_texts([text])[0]