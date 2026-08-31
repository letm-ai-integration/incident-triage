"""Log Analysis Agent: analyze mock logs and find errors."""
from __future__ import annotations

import logging
import pathlib
from typing import Optional

from app.agents.investigation.log_analysis.parser import LogAnalysisResult, parse_log_analysis_response
from app.agents.investigation.log_analysis.prompt import build_log_analysis_prompt
from app.domain.models.classification import ClassificationResult
from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.incident import Incident
from app.guardrails.prompt_injection import check_prompt_injection
from app.llm.client import create_structured_agent
from app.knowledge.retriever import RetrievedChunk, retrieve
from app.knowledge.vector_store import VectorStoreCollectionMissing
from app.logging_utils import (
    subagent_entry,
    subagent_output,
    subagent_process,
    subagent_exit,
    subagent_error,
)
from app.tools.mock.logs import MockLogTool

SYSTEM_PROMPT_PATH = pathlib.Path(__file__).parent.parent.parent.parent / "prompts" / "templates" / "log_analysis.txt"
with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

logger = logging.getLogger(__name__)

_SIGNALS = (
    "error", "fail", "timeout", "exception", "connection", "refused",
    "crash", "oom", "unavailable", "exhausted", "back off",
)

AGENT_NAME = "LogAnalysisAgent"
LOG_COLLECTION = "logs"


def _build_query(
    incident: Incident, classification: Optional[ClassificationResult] = None
) -> str:
    """Turn incident context into the natural-language query for the log RAG."""
    parts: list[str] = []
    if classification is not None:
        parts.append(f"incident type: {classification.incident_type.value}")
    title = (incident.title or "").strip()
    description = (incident.description or "").strip()
    if title:
        parts.append(f"title: {title}")
    if description:
        parts.append(f"description: {description}")
    if incident.service:
        parts.append(f"service: {incident.service}")
    return " ".join(parts)


def _retrieve_logs(
    incident: Incident,
    classification: Optional[ClassificationResult] = None,
    k: int = 3,
) -> tuple[list[RetrievedChunk], str]:
    """Query the model-data ``logs`` collection for incident-relevant evidence.

    Returns ``(chunks, error)`` -- ``chunks`` is empty and ``error`` is the
    reason when the ``logs`` collection is missing/unavailable, so the caller
    degrades gracefully instead of hallucinating log content.
    """
    query_text = _collect_query(incident, classification)
    subagent_process(AGENT_NAME, f"querying log RAG collection='{LOG_COLLECTION}'")
    try:
        chunks = retrieve(collection=LOG_COLLECTION, query_text=query_text, k=k)
    except VectorStoreCollectionMissing as exc:
        subagent_error(AGENT_NAME, exc, "log vector store not ingested")
        return [], str(exc)
    except Exception as exc:  # noqa: BLE001 -- degrade, never kill the run
        subagent_error(AGENT_NAME, exc, "log retrieval failed")
        return [], str(exc)
    if not chunks:
        subagent_process(AGENT_NAME, "log RAG returned no documents")
        return [], "No log documents retrieved for query."
    subagent_process(
        AGENT_NAME,
        f"retrieved {len(chunks)} log documents "
        f"(top_service={chunks[0].metadata.get('service')})",
    )
    return chunks, ""


def _collect_query(
    incident: Incident, classification: Optional[ClassificationResult] = None
) -> str:
    return _build_query(incident, classification)


def _keyword_signals(texts: list[str]) -> list[str]:
    lowered = [t.lower() for t in texts if t]
    return [kw for kw in _SIGNALS if any(kw in t for t in lowered)]


def _tag_retrieval_meta(
    result: "LogAnalysisResult",
    retrieved: list[RetrievedChunk],
    retrieval_error: str,
) -> "LogAnalysisResult":
    """Attach retrieval provenance to the first evidence item.

    Keeps the produced finding visibly grounded in *model-data* so the caller
    can prove the agent did not hallucinate.
    """
    raw = {
        "retrieved_documents": len(retrieved),
        "retrieved_services": sorted(
            {c.metadata.get("service") for c in retrieved if c.metadata.get("service")}
        ),
    }
    if retrieval_error:
        raw["retrieval_error"] = retrieval_error
    if result.evidence:
        result.evidence[0].raw_data.update(raw)
    return result


async def analyze_logs(
    incident: Incident,
    classification: Optional[ClassificationResult] = None,
    model: str | None = None,
) -> LogAnalysisResult:
    """Analyze application and system logs retrieved from the model-data RAG."""
    subagent_entry(AGENT_NAME, f"incident={incident.incident_id} llm_backed=True")

    # 1. Retrieve grounded log evidence from the model-data ``logs`` collection
    retrieved, retrieval_error = _retrieve_logs(incident, classification)
    if retrieved:
        logs_text = "\n\n".join(chunk.text for chunk in retrieved)
    else:
        logs_text = "\n".join(incident.raw_logs) if incident.raw_logs else ""
        if not logs_text:
            logs_text = "No log evidence available for this incident."

    # 2. Build user prompt from the retrieved (model-data) logs
    user_prompt = build_log_analysis_prompt(incident, logs_text)

    guard_result = check_prompt_injection("log_analysis", user_prompt)
    if not guard_result.passed:
        logger.warning(
            "[log_analysis.agent] prompt-injection guardrail flagged incident=%s findings=%s",
            incident.incident_id,
            guard_result.findings,
        )

    # 3. Create structured agent
    agent = create_structured_agent(
        system_prompt=SYSTEM_PROMPT,
        output_schema=LogAnalysisResult,
        model=model,
    )

    # 4. Invoke LLM asynchronously
    response = await agent.ainvoke(
        {
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        }
    )

    # 5. Parse response
    result = parse_log_analysis_response(response)
    result = _tag_retrieval_meta(result, retrieved, retrieval_error)
    subagent_output(
        AGENT_NAME,
        f"severity='{'high' if result.summary and 'error' in result.summary.lower() else 'info'}' "
        f"evidence_count={len(result.evidence)} retrieved={len(retrieved)}",
    )
    subagent_exit(AGENT_NAME)
    return result


def _deterministic_analysis(incident: Incident) -> LogAnalysisResult:
    """Deterministic keyword fallback grounded in the retrieved model-data logs.

    Queries the ``logs`` RAG collection for incident-specific evidence (the
    same data the LLM path would see) and scans the *retrieved* lines -- not
    just the incident's own ``raw_logs`` -- for known error signals.
    """
    retrieved, retrieval_error = _retrieve_logs(incident)
    retrieved_text = "\n".join(chunk.text for chunk in retrieved)

    texts = list(incident.raw_logs) + [incident.description]
    if retrieved_text:
        texts.append(retrieved_text)
    texts += [
        str(a.get("alert_name") or a.get("name") or "") if isinstance(a, dict) else str(a)
        for a in incident.raw_alerts
    ]
    matched_signals = _keyword_signals(texts)

    if retrieved and matched_signals:
        finding = (
            "Found error signals in retrieved model-data logs: "
            f"{', '.join(matched_signals[:5])}."
        )
        severity = "high"
    elif retrieved and not matched_signals:
        finding = (
            f"Retrieved {len(retrieved)} model-log document(s) for service "
            f"'{retrieved[0].metadata.get('service') or incident.service}' "
            "but no explicit error signals matched; reviewed as informational."
        )
        severity = "info"
    elif not retrieved:
        finding = (
            f"Log RAG collection unavailable ({retrieval_error}) - no grounded log "
            "evidence to analyze."
        )
        severity = "info"
    else:
        finding = "No error signals detected in logs."
        severity = "info"

    evidence = Evidence(
        evidence_id="ev-log-1",
        source="log_analysis",
        finding=finding,
        severity=severity,
        raw_data={
            "matched_signals": matched_signals[:10],
            "retrieved_documents": len(retrieved),
            "retrieved_services": sorted(
                {r.metadata.get("service") for r in retrieved if r.metadata.get("service")}
            ),
            "log_count": len(incident.raw_logs),
        },
    )
    hypothesis = Hypothesis(
        hypothesis_id="hyp-log-1",
        description=f"Log analysis indicates: {finding}",
        confidence=0.7 if matched_signals else 0.3,
        supporting_evidence=["ev-log-1"],
        contradicting_evidence=[],
        label=HypothesisLabel.LIKELY if matched_signals else HypothesisLabel.POSSIBLE,
    )
    return LogAnalysisResult(
        evidence=[evidence],
        hypotheses=[hypothesis],
        summary=finding,
    )


async def analyze_logs_with_fallback(
    incident: Incident,
    classification: Optional[ClassificationResult] = None,
    llm=None,
) -> LogAnalysisResult:
    """Always execute log analysis. Uses LLM when available, else deterministic fallback.

    This is the entry point used by the orchestrator to ensure the subagent
    genuinely executes in every mode.
    """
    subagent_entry(AGENT_NAME, f"incident={incident.incident_id} llm_backed={llm is not None}")
    try:
        if llm is not None:
            try:
                result = await analyze_logs(incident, classification)
            except Exception as exc:
                logger.warning(
                    "[log_analysis.agent] LLM analysis failed (%s: %s); using deterministic fallback",
                    type(exc).__name__,
                    exc,
                )
                subagent_error(AGENT_NAME, exc, "LLM failed, falling back to deterministic")
                result = _deterministic_analysis(incident)
        else:
            result = _deterministic_analysis(incident)
        subagent_output(AGENT_NAME, f"severity={'high' if result.summary and 'error' in result.summary.lower() else 'info'} evidence_count={len(result.evidence)}")
    except Exception as exc:
        subagent_error(AGENT_NAME, exc)
        raise
    finally:
        subagent_exit(AGENT_NAME)
    return result


class LogAnalysisAgent:
    """Backward-compatible class wrapper around :func:`analyze_logs`.

    Restored after commit c584fa0 replaced the original class with a
    function-based structured agent; ``app.agents.investigation.orchestrator``
    (and any other callers) still expect ``LogAnalysisAgent(llm, tool).run(...)``.
    """

    def __init__(self, llm=None, mock_tool: MockLogTool | None = None):
        self.llm = llm
        self.mock_tool = mock_tool

    async def run(
        self,
        incident: Incident,
        classification: Optional[ClassificationResult] = None,
    ) -> LogAnalysisResult:
        return await analyze_logs(incident, classification)
