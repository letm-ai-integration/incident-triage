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

from app.knowledge.ingest import ingest_file_into_collection


def main() -> None:
    parser = argparse.ArgumentParser(description="Manually ingest a knowledge markdown file into the vector store.")
    parser.add_argument("--file", required=True, help="Path to the markdown knowledge source.")
    parser.add_argument("--collection", required=True, help="Vector-store collection name for this domain.")
    args = parser.parse_args()

    count = ingest_file_into_collection(args.file, args.collection)
    if count == 0:
        print(f"No '## ' sections found in {args.file} — nothing to ingest.")
    else:
        print(f"Ingested {count} chunks from {args.file} into collection '{args.collection}'.")


if __name__ == "__main__":
    main()