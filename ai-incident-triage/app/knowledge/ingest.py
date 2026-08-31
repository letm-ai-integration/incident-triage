"""
Core knowledge ingestion logic.

Refactored out of scripts/ingest_knowledge.py to allow both manual ingestion
and automated runbook learning to share the same chunking/embedding pathway.
"""
from __future__ import annotations

import logging
from app.knowledge.chunker import chunk_markdown_by_sections
from app.knowledge.loader import load_markdown_file
from app.knowledge.vector_store import add_documents

logger = logging.getLogger(__name__)

def ingest_file_into_collection(file_path: str, collection_name: str) -> int:
    """Read a markdown file, chunk it by sections, and upsert into the vector store."""
    try:
        text = load_markdown_file(file_path)
    except FileNotFoundError:
        logger.error(f"Cannot ingest {file_path} - file not found.")
        return 0

    chunks = chunk_markdown_by_sections(text, source_file=file_path)
    
    if not chunks:
        logger.warning(f"No '## ' sections found in {file_path} — nothing to ingest.")
        return 0

    add_documents(
        collection_name=collection_name,
        docs=[chunk.text for chunk in chunks],
        metadatas=[chunk.metadata for chunk in chunks],
        ids=[chunk.chunk_id for chunk in chunks],
    )
    logger.info(f"Ingested {len(chunks)} chunks from {file_path} into collection '{collection_name}'.")
    return len(chunks)
