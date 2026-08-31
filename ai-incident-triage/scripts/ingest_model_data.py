"""Ingest the real mock data under ``model-data`` into the shared FAISS vector store.

This is the canonical rebuild entry point for the RAG used by the Log and
Kubernetes investigation agents (and the shared runbook retrieval). It reads
the physical files under ``model-data`` directly -- the same files the incident
JSONs under ``data/incidents`` reference -- and pushes service-aligned chunks
into per-domain FAISS collections:

    model-data/db_logs.txt            \
    model-data/external_api_logs.txt   |> ``logs`` collection
    model-data/logs_traces.txt        /
    model-data/metrics.json           → ``metrics`` collection
    model-data/k8s_logs.json          → ``k8s``   collection
    model-data/deployment_events.json → ``events`` collection
    knowledge_base/runbooks/*.md + runbooks/*.md → ``runbooks`` collection

Run this after any mock-data change so retrieval reflects the new incidents:

    python scripts/ingest_model_data.py            # everything
    python scripts/ingest_model_data.py --collections logs k8s
    python scripts/ingest_model_data.py --collections runbooks

Ingestion is idempotent: ``add_documents`` upserts by id, so re-running is safe
and only adds/updates what changed.
"""
from __future__ import annotations

import argparse
import sys

from app.knowledge.chunker import chunk_markdown_by_sections
from app.knowledge.model_data import collection_source, runbook_md
from app.knowledge.vector_store import add_documents

ALL_COLLECTIONS = ("logs", "k8s", "metrics", "events", "runbooks")


def _ingest_runbooks() -> int:
    """Feed the ``runbooks`` collection from its markdown knowledge sources."""
    total = 0
    sources: list[tuple[str, str]] = []

    curated = runbook_md()
    if curated:
        sources.append(("knowledge_base/runbooks/runbook.md", curated))

    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    runbooks_dir = repo_root / "runbooks"
    for md in sorted(runbooks_dir.glob("*.md")):
        sources.append((str(md.relative_to(repo_root)), md.read_text(encoding="utf-8")))

    if not sources:
        print("No runbook sources found -- nothing ingested into 'runbooks'.")
        return 0

    for source, text in sources:
        chunks = chunk_markdown_by_sections(text, source_file=source)
        if not chunks:
            continue
        add_documents(
            collection_name="runbooks",
            docs=[c.text for c in chunks],
            metadatas=[c.metadata for c in chunks],
            ids=[c.chunk_id for c in chunks],
        )
        total += len(chunks)
        print(f"  ingested {len(chunks)} chunk(s) from {source}")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild RAG collections from model-data.")
    parser.add_argument(
        "--collections",
        nargs="+",
        default=list(ALL_COLLECTIONS),
        help=(
            "Subset of collections to ingest: "
            + ", ".join(ALL_COLLECTIONS)
            + ". Default: all."
        ),
    )
    args = parser.parse_args()

    requested = [c for c in args.collections if c in ALL_COLLECTIONS]
    if not requested:
        print(f"No valid collections requested. Valid: {', '.join(ALL_COLLECTIONS)}")
        sys.exit(1)

    print("Rebuilding knowledge collections from model-data ...")
    total = 0
    for collection in requested:
        if collection == "runbooks":
            total += _ingest_runbooks()
            continue
        chunks = collection_source(collection)
        if not chunks:
            print(f"  no model-data chunks for collection '{collection}'")
            continue
        add_documents(
            collection_name=collection,
            docs=[c.doc for c in chunks],
            metadatas=[c.metadata for c in chunks],
            ids=[c.doc_id for c in chunks],
        )
        print(f"  ingested {len(chunks)} chunk(s) into '{collection}'")
        total += len(chunks)

    print(f"Done. {total} chunks ingested across {len(requested)} collection(s).")
    print("Rerun this script after any model-data edit so retrieval reflects it.")


if __name__ == "__main__":
    main()