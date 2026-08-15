"""
Structural chunker for the project's markdown knowledge files.

Chunks by ``## `` section, not by fixed token windows -- each alert/entry stays
whole, since splitting mid-entry would break retrieval quality for this format.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SECTION_RE = re.compile(r"^## (.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    title: str
    text: str
    metadata: dict


def chunk_markdown_by_sections(
    text: str, source_file: str, extra_metadata: dict | None = None
) -> list[Chunk]:
    """Split ``text`` into one ``Chunk`` per ``## `` heading."""
    headers = list(SECTION_RE.finditer(text))
    chunks = []
    for i, header in enumerate(headers):
        start = header.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        section_text = text[start:end].strip()
        title = header.group(1).strip()
        chunk_id = f"{source_file}::{i}::{title[:40]}"
        metadata = {"source_file": source_file, "title": title}
        if extra_metadata:
            metadata.update(extra_metadata)
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                title=title,
                text=f"## {title}\n\n{section_text}",
                metadata=metadata,
            )
        )
    return chunks