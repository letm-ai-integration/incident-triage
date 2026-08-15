"""Tests for the markdown section chunker."""

from app.knowledge.chunker import chunk_markdown_by_sections

SAMPLE = """# Incident Runbook Knowledge Base

## High API Failures

**Alert:** More than 10 HTTP 5xx errors per minute

**Solution:**
- Roll back immediately.

---

## Pod CrashLoopBackOff (OOMKilled)

**Alert:** Pod restart count > 5

**Solution:**
- Raise memory limit.

---

## ImagePullBackOff

**Alert:** Pod stuck in ImagePullBackOff

**Solution:**
- Fix image tag.
"""


def test_splits_into_expected_number_of_chunks():
    chunks = chunk_markdown_by_sections(SAMPLE, source_file="runbook.md")
    assert len(chunks) == 3


def test_chunk_titles_and_ids():
    chunks = chunk_markdown_by_sections(SAMPLE, source_file="runbook.md")
    assert [c.title for c in chunks] == [
        "High API Failures",
        "Pod CrashLoopBackOff (OOMKilled)",
        "ImagePullBackOff",
    ]
    assert chunks[0].chunk_id == "runbook.md::0::High API Failures"
    assert chunks[1].chunk_id == "runbook.md::1::Pod CrashLoopBackOff (OOMKilled)"


def test_chunk_contains_full_section():
    chunks = chunk_markdown_by_sections(SAMPLE, source_file="runbook.md")
    assert "**Alert:** More than 10 HTTP 5xx errors per minute" in chunks[0].text
    assert "**Solution:**" in chunks[0].text
    assert "Roll back immediately." in chunks[0].text
    # Section boundaries must not bleed into the next section.
    assert "Pod restart count" not in chunks[0].text


def test_metadata_and_extra_metadata():
    chunks = chunk_markdown_by_sections(
        SAMPLE, source_file="runbook.md", extra_metadata={"domain": "runbooks"}
    )
    assert chunks[0].metadata["source_file"] == "runbook.md"
    assert chunks[0].metadata["title"] == "High API Failures"
    assert chunks[0].metadata["domain"] == "runbooks"


def test_no_sections_returns_empty():
    assert chunk_markdown_by_sections("no headings here", source_file="x.md") == []


def test_single_section_only():
    text = "# T\n\n## Only One\n\nbody"
    chunks = chunk_markdown_by_sections(text, source_file="x.md")
    assert len(chunks) == 1
    assert chunks[0].title == "Only One"
