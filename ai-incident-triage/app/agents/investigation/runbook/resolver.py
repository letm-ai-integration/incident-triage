"""Resolve a runbook by *incident name* from the on-disk ``runbooks/*.md`` files.

The FAISS ``runbooks`` collection tells the investigation *whether* a runbook is
relevant; but the final result needs to (a) be keyed by the incident name and
(b) surface the runbook's actual **Solution**. This module owns that name→file
resolution.

Each ``runbooks/*.md`` file follows the convention::

    # <Incident Display Name>

    ## Overview
    ...

    ## Solution
    <the resolution text>

    ## Troubleshooting
    ...

``resolve_by_name`` token-matches the incident title/description against each
runbook's display name and returns the best match (or ``None``). It never makes
things up: if no runbook name overlaps the incident, the system proceeds with
normal analysis (``RunbookStatus.NO_MATCH`` / no solution).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.domain.models.classification import ClassificationResult

RUNBOOKS_DIR_NAME = "runbooks"


@dataclass(frozen=True)
class RunbookDoc:
    """A parsed runbook file: name, path and the sections we reuse."""

    name: str
    file: str
    overview: str = ""
    solution: str = ""
    keywords: tuple[str, ...] = field(default_factory=tuple)


def _runbooks_dir() -> Path:
    # resolver.py lives at app/agents/investigation/runbook/resolver.py; five
    # levels up is the repo root that holds the ``runbooks/`` directory.
    return Path(__file__).resolve().parents[4] / RUNBOOKS_DIR_NAME


def _normalize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    # Drop generic stop-words that add no discrimination when matching names.
    stop = {"the", "a", "an", "of", "on", "for", "and", "or", "in", "to", "is", "service"}
    return {w for w in words if w not in stop}


def _section(lines: list[str], title: str) -> str:
    title = title.lower()
    capture: list[str] = []
    active = False
    for raw in lines:
        if re.match(r"^#{1,6}\s+", raw):
            heading = raw.lstrip("#").strip().lower()
            if heading == title:
                active = True
                continue
            active = False
        if active:
            capture.append(raw)
    return "\n".join(capture).strip()


def load_runbooks() -> list[RunbookDoc]:
    """Scan ``runbooks/*.md`` and parse name + solution for each."""
    docs: list[RunbookDoc] = []
    directory = _runbooks_dir()
    if not directory.is_dir():
        return docs
    for md in sorted(directory.glob("*.md")):
        lines = md.read_text(encoding="utf-8").splitlines()
        name = None
        for raw in lines:
            m = re.match(r"^#\s+(.+)$", raw)
            if m:
                name = m.group(1).strip()
                break
        if not name:
            continue
        docs.append(
            RunbookDoc(
                name=name,
                file=str(md.relative_to(directory.parent)),
                overview=_section(lines, "overview"),
                solution=_section(lines, "solution"),
                keywords=tuple(sorted(_normalize(name))),
            )
        )
    return docs


def resolve_by_name(
    title: str, description: str = "", classification: ClassificationResult | None = None
) -> RunbookDoc | None:
    """Return the runbook whose display name best overlaps the incident text.

    Uses exact/contained token overlap between the runbook name and the incident
    title (+ description). Only returns a doc with a supported ``## Solution``.
    """
    incident_tokens = _normalize(f"{title} {description}")
    if not incident_tokens:
        return None

    best: RunbookDoc | None = None
    best_hits = 0
    for doc in load_runbooks():
        name_tokens = set(doc.keywords)
        hits = len(incident_tokens & name_tokens)
        # A runbook whose name is fully contained in the incident is a strong hint.
        if name_tokens and name_tokens <= incident_tokens:
            hits += len(name_tokens)
        if hits > best_hits and doc.solution:
            best_hits = hits
            best = doc
    return best if best_hits > 0 else None