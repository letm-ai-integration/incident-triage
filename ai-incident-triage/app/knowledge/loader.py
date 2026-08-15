"""
Reads a markdown source file from disk.

Kept separate from chunking so future non-markdown sources (if any) can plug in
without touching chunker.py.
"""
from __future__ import annotations

from pathlib import Path


def load_markdown_file(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Knowledge source file not found: {path}")
    return path.read_text(encoding="utf-8")