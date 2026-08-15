"""
Manual ingestion trigger. Run this whenever a knowledge source .md file has
been edited and should be reflected in search.

Usage:
    python scripts/ingest_knowledge.py --file knowledge_base/runbooks/runbook.md --collection runbooks

The same script, unchanged, ingests any future domain (e.g. logs, k8s):
    python scripts/ingest_knowledge.py --file knowledge_base/logs/logs.md --collection logs
"""
from __future__ import annotations

import argparse

from app.knowledge.chunker import chunk_markdown_by_sections
from app.knowledge.loader import load_markdown_file
from app.knowledge.vector_store import add_documents


def main() -> None:
    parser = argparse.ArgumentParser(description="Manually ingest a knowledge markdown file into the vector store.")
    parser.add_argument("--file", required=True, help="Path to the markdown knowledge source.")
    parser.add_argument("--collection", required=True, help="Vector-store collection name for this domain.")
    args = parser.parse_args()

    text = load_markdown_file(args.file)
    chunks = chunk_markdown_by_sections(text, source_file=args.file)

    if not chunks:
        print(f"No '## ' sections found in {args.file} — nothing to ingest.")
        return

    add_documents(
        collection_name=args.collection,
        docs=[chunk.text for chunk in chunks],
        metadatas=[chunk.metadata for chunk in chunks],
        ids=[chunk.chunk_id for chunk in chunks],
    )
    print(
        f"Ingested {len(chunks)} chunks from {args.file} into collection '{args.collection}'."
    )


if __name__ == "__main__":
    main()