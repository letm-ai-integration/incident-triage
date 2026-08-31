"""Runbook Agent: retrieve a relevant runbook for an incident via shared RAG.

This agent no longer parses ``runbook.md`` directly at request time. The
knowledge base is ingested manually via ``scripts/ingest_knowledge.py`` into
the ``runbooks`` FAISS collection, and this agent only queries the vector
store. Retrieval is provider-agnostic: local FAISS + local sentence-transformer
embeddings, independent of the LLM provider configured for chat.
"""
from __future__ import annotations

import logging

from app.agents.investigation.runbook import resolver
from app.domain.models.classification import ClassificationResult
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.graph.state import RunbookResult, RunbookStatus
from app.knowledge.retriever import RetrievedChunk, retrieve
from app.knowledge.vector_store import VectorStoreCollectionMissing
from app.logging_utils import (
    subagent_entry,
    subagent_output,
    subagent_process,
    subagent_exit,
    subagent_error,
)

RUNBOOK_COLLECTION = "runbooks"
MIN_RELEVANCE_SCORE = 0.45  # cosine similarity; tuned against real scores (strong matches ~0.55-0.7, non-matches <0.15)

logger = logging.getLogger(__name__)

AGENT_NAME = "RunbookAgent"


def run_runbook_agent(alert_data: dict, classification: ClassificationResult | None = None) -> RunbookResult:
    """Search the runbook collection for ``alert_data`` and return a match result.

    Two complementary signals are used:

    1. A *name-based* lookup (``resolver.resolve_by_name``) that matches the
       incident against the on-disk ``runbooks/*.md`` files by incident name and
       extracts the runbook's actual **Solution**. This is what guarantees a
       runbook-backed resolution can be cited verbatim in the final result.
    2. A semantic FAISS retrieval over the ``runbooks`` collection for the
       relevance score used in evidence weighting.

    A solution is only ever returned if a named runbook actually exists with a
    ``## Solution`` section -- the agent never fabricates one.
    """
    query_text = _build_query(alert_data, classification)
    subagent_entry(AGENT_NAME, f"query_len={len(query_text)}")

    resolved = resolver.resolve_by_name(
        title=str(alert_data.get("title") or ""),
        description=str(alert_data.get("description") or ""),
        classification=classification,
    )

    # Collector for the FAISS relevance result (may leave MATCHED for a weak hit).
    faiss_result = None
    try:
        results = retrieve(collection=RUNBOOK_COLLECTION, query_text=query_text, k=3)
    except VectorStoreCollectionMissing as exc:
        logger.error("[runbook.agent] vector store collection missing: %s", exc)
        subagent_error(AGENT_NAME, exc)
        if resolved is not None and resolved.solution:
            _log_named_match(resolved)
            subagent_exit(AGENT_NAME)
            return _named_match_result(resolved)
        subagent_exit(AGENT_NAME)
        return RunbookResult(status=RunbookStatus.ERROR, error=f"{exc}")
    except Exception as exc:  # noqa: BLE001 -- surface any retrieval failure as ERROR (spec §6)
        logger.exception("[runbook.agent] retrieval failed")
        subagent_error(AGENT_NAME, exc)
        if resolved is not None and resolved.solution:
            _log_named_match(resolved)
            subagent_exit(AGENT_NAME)
            return _named_match_result(resolved)
        subagent_exit(AGENT_NAME)
        return RunbookResult(status=RunbookStatus.ERROR, error=f"Runbook search failed: {exc}")

    if results:
        top = results[0]
        subagent_process(
            AGENT_NAME,
            f"retrieved {len(results)} runbook candidate(s) "
            f"top_title={top.metadata.get('title')} score={top.score:.2f}",
        )
        if top.score >= MIN_RELEVANCE_SCORE:
            faiss_result = RunbookResult(
                status=RunbookStatus.MATCHED,
                matched_title=top.metadata.get("title"),
                score=top.score,
                hypothesis=_hypothesis_from_chunk(top),
            )
    else:
        subagent_process(AGENT_NAME, "no runbook candidates retrieved")

    # Prefer the name-based, solution-backed match whenever one exists.
    if resolved is not None and resolved.solution:
        _log_named_match(resolved)
        subagent_exit(AGENT_NAME)
        return _named_match_result(resolved, score=(faiss_result.score if faiss_result else None))

    if faiss_result is not None:
        logger.info(
            "[runbook.agent] MATCHED runbook title=%r score=%.2f",
            faiss_result.matched_title,
            faiss_result.score,
        )
        subagent_output(AGENT_NAME, f"MATCHED '{faiss_result.matched_title}' score={faiss_result.score:.2f}")
        subagent_exit(AGENT_NAME)
        return faiss_result

    logger.info("[runbook.agent] no candidates retrieved for query")
    subagent_output(AGENT_NAME, "no candidates found")
    subagent_exit(AGENT_NAME)
    return RunbookResult(status=RunbookStatus.NO_MATCH)


def _log_named_match(doc: "RunbookDoc") -> None:
    logger.info("[runbook.agent] name-matched runbook '%s' with solution", doc.name)
    subagent_output(AGENT_NAME, f"name-matched runbook '{doc.name}' (solution found)")


def _named_match_result(doc: "RunbookDoc", score: float | None = None) -> RunbookResult:
    """Build a ``MATCHED`` result carrying the runbook's name + solution text."""
    confidence = max(score or 0.0, MIN_RELEVANCE_SCORE)
    hypothesis = Hypothesis(
        hypothesis_id=f"runbook-name-{len(doc.keywords)}",
        description=f"## {doc.name}\n\n{doc.overview}\n\n**Solution:**\n{doc.solution}",
        confidence=confidence,
        supporting_evidence=[f"runbook:{doc.file}:{doc.name}"],
        contradicting_evidence=[],
        label=HypothesisLabel.LIKELY if confidence >= 0.8 else HypothesisLabel.POSSIBLE,
    )
    return RunbookResult(
        status=RunbookStatus.MATCHED,
        hypothesis=hypothesis,
        matched_title=doc.name,
        runbook_name=doc.name,
        solution=doc.solution,
        resolution=f"A matching runbook was found for \"{doc.name}\". "
                   f"The recommended resolution from the runbook is: {doc.solution}",
        score=confidence,
    )


def _hypothesis_from_chunk(chunk: "RetrievedChunk") -> Hypothesis:
    return Hypothesis(
        hypothesis_id=f"runbook-{RUNBOOK_COLLECTION}-faiss",
        description=chunk.text,
        confidence=chunk.score,
        supporting_evidence=[f"runbook:{chunk.metadata.get('source_file')}:{chunk.metadata.get('title')}"],
        contradicting_evidence=[],
        label=HypothesisLabel.LIKELY if chunk.score >= 0.8 else HypothesisLabel.POSSIBLE,
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