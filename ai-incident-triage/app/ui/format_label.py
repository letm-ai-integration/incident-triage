"""Humanize internal node / sub-agent identifiers for display (Phase 4).

Raw identifiers such as ``rca_report`` or ``log_analysis`` read like
exposed code/variable names in a product UI. This module is the single
display-only transformation used *everywhere* a node or sub-agent name is
rendered (graph canvas boxes/pills, sub-agent pills, the Active Node Detail
row, the execution timeline). It never renames graph nodes or event keys --
the underlying identifiers stay untouched.

Override dictionary first (known acronyms / proper nouns), then a generic
split-on-underscores + title-case fallback so any future node name gets a
reasonable default without a code change.
"""

from __future__ import annotations

# Known acronyms / proper nouns that must not be naively title-cased.
_OVERRIDES: dict[str, str] = {
    "rca": "RCA",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "api": "API",
    "db": "DB",
    "dns": "DNS",
    "tls": "TLS",
    "http": "HTTP",
    "llm": "LLM",
    "rag": "RAG",
    "ui": "UI",
    "id": "ID",
    "ids": "IDs",
    "url": "URL",
    "urls": "URLs",
    "s3": "S3",
    "aws": "AWS",
    "gcp": "GCP",
    "iam": "IAM",
    "cpu": "CPU",
    "mem": "MEM",
    "sql": "SQL",
    "sla": "SLA",
}

# Whole-name overrides win before any word-level processing.
_NAME_OVERRIDES: dict[str, str] = {
    "rca_report": "RCA Report",
    "k8s_diagnostics": "Kubernetes Diagnostics",
}


def humanize_node_name(name: str | None) -> str:
    """``log_analysis`` -> ``Log Analysis``, ``rca_report`` -> ``RCA Report``.

    Order: exact-name override -> per-word overrides -> generic title-case.
    Already all-caps words (length > 1) are preserved as-is.
    """
    if not name:
        return "" if name is None else str(name)
    name = str(name)
    if name in _NAME_OVERRIDES:
        return _NAME_OVERRIDES[name]
    words: list[str] = []
    for word in name.split("_"):
        if not word:
            continue
        if word in _OVERRIDES:
            words.append(_OVERRIDES[word])
        elif len(word) > 1 and word.isupper():
            words.append(word)  # preserve existing acronyms, e.g. "AWS"
        else:
            words.append(word[:1].upper() + word[1:])
    return " ".join(words) if words else name


__all__ = ["humanize_node_name"]
