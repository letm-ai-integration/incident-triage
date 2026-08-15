"""Runbook Agent: retrieve a relevant runbook for an incident via shared RAG.

This agent no longer parses ``runbook.md`` directly at request time. The
knowledge base is ingested manually via ``scripts/ingest_knowledge.py`` into
the ``runbooks`` FAISS collection, and this agent only queries the vector
store. Retrieval is provider-agnostic: local FAISS + local sentence-transformer
embeddings, independent of the LLM provider configured for chat.
"""
from __future__ import annotations

from app.domain.models.classification import ClassificationResult
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.graph.state import RunbookResult, RunbookStatus
from app.knowledge.retriever import retrieve
from app.knowledge.vector_store import VectorStoreCollectionMissing

RUNBOOK_COLLECTION = "runbooks"
MIN_RELEVANCE_SCORE = 0.45  # cosine similarity; tuned against real scores (strong matches ~0.55-0.7, non-matches <0.15)


def run_runbook_agent(alert_data: dict, classification: ClassificationResult | None = None) -> RunbookResult:
    """Search the runbook collection for ``alert_data`` and return a match result."""
    query_text = _build_query(alert_data, classification)

    try:
        results = retrieve(collection=RUNBOOK_COLLECTION, query_text=query_text, k=3)
    except VectorStoreCollectionMissing as exc:
        return RunbookResult(
            status=RunbookStatus.ERROR,
            error=f"{exc}",
        )
    except Exception as exc:  # noqa: BLE001 -- surface any retrieval failure as ERROR (spec §6)
        return RunbookResult(status=RunbookStatus.ERROR, error=f"Runbook search failed: {exc}")

    if not results:
        return RunbookResult(status=RunbookStatus.NO_MATCH)

    top = results[0]
    if top.score < MIN_RELEVANCE_SCORE:
        return RunbookResult(status=RunbookStatus.NO_MATCH)

    hypothesis = Hypothesis(
        hypothesis_id=f"runbook-{RUNBOOK_COLLECTION}-{len(results)}",
        description=top.text,
        confidence=top.score,
        supporting_evidence=[f"runbook:{top.metadata.get('source_file')}:{top.metadata.get('title')}"],
        contradicting_evidence=[],
        label=HypothesisLabel.LIKELY if top.score >= 0.8 else HypothesisLabel.POSSIBLE,
    )
    return RunbookResult(
        status=RunbookStatus.MATCHED,
        hypothesis=hypothesis,
        matched_title=top.metadata.get("title"),
        score=top.score,
    )


def _build_query(alert_data: dict, classification: ClassificationResult | None = None) -> str:
    """Build the natural-language query sent to the retriever.

    Prefer classification fields (incident_type, priority, description) when
    available, since they carry the richest signal for the embedding model.
    """
    parts: list[str] = []

    if classification is not None:
        parts.append(f"incident type: {classification.incident_type.value}")
        parts.append(f"priority: {classification.priority.value}")
        if classification.affected_services:
            parts.append(f"affected services: {', '.join(classification.affected_services)}")

    title = str(alert_data.get("title") or "").strip()
    description = str(alert_data.get("description") or "").strip()
    if title:
        parts.append(f"title: {title}")
    if description:
        parts.append(f"description: {description}")

    logs = " ".join(str(item) for item in alert_data.get("raw_logs", [])).strip()
    if logs:
        parts.append(f"logs: {logs}")

    return " ".join(parts) if parts else str(alert_data)