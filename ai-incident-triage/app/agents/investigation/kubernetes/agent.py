"""Kubernetes Agent: analyze mock K8s data, events & resources."""
from __future__ import annotations

import logging
import re
from typing import Optional

from app.agents.investigation.kubernetes.parser import KubernetesAnalysisResult, parse_kubernetes_response
from app.agents.investigation.kubernetes.prompt import build_kubernetes_prompt
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
from app.tools.mock.kubernetes import MockKubernetesTool, MockKubernetesToolOutput

import pathlib
SYSTEM_PROMPT_PATH = pathlib.Path(__file__).parent.parent.parent.parent / "prompts" / "templates" / "kubernetes.txt"
with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

logger = logging.getLogger(__name__)

_SIGNALS = (
    "error", "fail", "timeout", "exception", "connection", "refused",
    "crash", "oom", "unavailable", "exhausted", "back off",
)

AGENT_NAME = "KubernetesAnalysisAgent"
K8S_COLLECTION = "k8s"

_K8S_EVENT_SIGNALS = (
    "CrashLoopBackOff", "OOMKilled", "ImagePullBackOff", "Back-off",
    "FailedToStart", "Unschedulable", "Eviction", "restart",
)


def _keyword_signals(texts: list[str]) -> list[str]:
    lowered = [t.lower() for t in texts if t]
    return [kw for kw in _SIGNALS if any(kw in t for t in lowered)]


def _build_query(
    incident: Incident, classification: Optional[ClassificationResult] = None
) -> str:
    parts: list[str] = []
    if classification is not None:
        parts.append(f"k8s incident type: {classification.incident_type.value}")
    if incident.title:
        parts.append(f"pod/workload: {incident.title}")
    if incident.description:
        parts.append(f"description: {incident.description}")
    if incident.service:
        parts.append(f"service: {incident.service}")
    namespace = incident.metadata.get("namespace") if isinstance(incident.metadata, dict) else None
    if namespace:
        parts.append(f"namespace: {namespace}")
    return " ".join(parts)


def _retrieve_k8s(incident, classification, k: int = 3):
    """Query the model-data ``k8s`` collection for incident-relevant pod events."""
    query_text = _build_query(incident, classification)
    subagent_process(AGENT_NAME, f"querying k8s RAG collection='{K8S_COLLECTION}'")
    try:
        chunks = retrieve(collection=K8S_COLLECTION, query_text=query_text, k=k)
    except VectorStoreCollectionMissing as exc:
        subagent_error(AGENT_NAME, exc, "k8s vector store not ingested")
        return [], str(exc)
    except Exception as exc:  # noqa: BLE001 -- degrade, never kill the run
        subagent_error(AGENT_NAME, exc, "k8s retrieval failed")
        return [], str(exc)
    if not chunks:
        subagent_process(AGENT_NAME, "k8s RAG returned no documents")
        return [], "No kubernetes documents retrieved for query."
    subagent_process(
        AGENT_NAME,
        f"retrieved {len(chunks)} k8s documents "
        f"(top_namespace={chunks[0].metadata.get('namespace')})",
    )
    return chunks, ""


def _k8s_summary(chunks: list[RetrievedChunk]) -> dict:
    """Condense retrieved k8s chunks into concise metadata the agents surface.

    Counts how many distinct namespaces/pods were seen and which degradation
    signals (OOMKilled, CrashLoopBackOff, ImagePullBackOff, restarts) appear.
    """
    text = "\n".join(c.text for c in chunks)
    signals = [s for s in _K8S_EVENT_SIGNALS if s.lower() in text.lower()]
    namespaces = sorted({c.metadata.get("namespace") for c in chunks if c.metadata.get("namespace")})
    services = sorted({c.metadata.get("service") for c in chunks if c.metadata.get("service")})
    return {
        "retrieved_documents": len(chunks),
        "namespaces": namespaces,
        "services": services,
        "event_signals": signals,
    }


async def analyze_kubernetes(
    incident: Incident,
    classification: Optional[ClassificationResult] = None,
    model: str | None = None,
) -> KubernetesAnalysisResult:
    """Analyze Kubernetes telemetry retrieved from the model-data ``k8s`` RAG."""
    subagent_entry(AGENT_NAME, f"incident={incident.incident_id} llm_backed=True")

    # 1. Retrieve grounded k8s evidence from the model-data ``k8s`` collection
    retrieved, retrieval_error = _retrieve_k8s(incident, classification)
    if retrieved:
        k8s_text = "\n\n".join(chunk.text for chunk in retrieved)
        proximity = dict(
            service=incident.service,
            namespace=incident.metadata.get("namespace", "default")
            if isinstance(incident.metadata, dict)
            else "default",
            pod_statuses=[],
            recent_events=k8s_text.splitlines(),
            resource_usage={},
        )
        tool_output = MockKubernetesToolOutput(**proximity)
    else:
        tool_output = MockKubernetesToolOutput(
            service=incident.service,
            namespace=incident.metadata.get("namespace", "default")
            if isinstance(incident.metadata, dict)
            else "default",
            pod_statuses=[],
            recent_events=[],
            resource_usage={},
        )

    # 2. Build user prompt from the retrieved (model-data) k8s evidence
    user_prompt = build_kubernetes_prompt(incident, tool_output)

    guard_result = check_prompt_injection("kubernetes", user_prompt)
    if not guard_result.passed:
        logger.warning(
            "[kubernetes.agent] prompt-injection guardrail flagged incident=%s findings=%s",
            incident.incident_id,
            guard_result.findings,
        )

    # 3. Create structured agent
    agent = create_structured_agent(
        system_prompt=SYSTEM_PROMPT,
        output_schema=KubernetesAnalysisResult,
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
    result = parse_kubernetes_response(response)
    _tag_k8s_meta(result, retrieved, retrieval_error)
    subagent_output(
        AGENT_NAME,
        f"evidence_count={len(result.evidence)} retrieved={len(retrieved)} "
        f"degraded={bool(result.hypotheses)}",
    )
    subagent_exit(AGENT_NAME)
    return result


def _tag_k8s_meta(
    result: "KubernetesAnalysisResult",
    retrieved: list[RetrievedChunk],
    retrieval_error: str,
) -> "KubernetesAnalysisResult":
    raw = _k8s_summary(retrieved) if retrieved else {"retrieved_documents": 0}
    if retrieval_error:
        raw["retrieval_error"] = retrieval_error
    if result.evidence:
        result.evidence[0].raw_data.update(raw)
    return result


def _service_tokens(value: str | None) -> set[str]:
    """Meaningful lowercase tokens of a service/pod identifier."""
    return {t for t in re.split(r"[^a-z0-9]+", (value or "").lower()) if len(t) >= 4}


def _services_relate(incident_service: str | None, retrieved_services) -> bool:
    """True when ANY retrieved chunk service belongs to the incident's service.

    Prevents cross-incident contamination: a fictional/unsynchronized service
    must not be flagged degraded just because *other* services' model-data
    happens to contain generic words like error/fail/restart.
    """
    inc = _service_tokens(incident_service)
    if not inc:
        return False
    for svc in retrieved_services or []:
        if svc and (_service_tokens(str(svc)) & inc):
            return True
    return False


def _deterministic_analysis(incident: Incident) -> KubernetesAnalysisResult:
    """Deterministic keyword fallback grounded in the retrieved model-data k8s.

    Queries the ``k8s`` RAG collection for incident-relevant pod events and
    flags degradation based on the *retrieved* model-data evidence (and the
    incident's own events/alerts) -- never a canned answer.
    """
    retrieved, retrieval_error = _retrieve_k8s(incident, None)
    retrieved_text = "\n".join(chunk.text for chunk in retrieved)

    events_text = " ".join(str(e) for e in incident.raw_events)
    alerts = " ".join(
        str(a.get("alert_name") or a.get("name") or "") if isinstance(a, dict) else str(a)
        for a in incident.raw_alerts
    )

    # Signals seen in the incident's OWN payload always count ...
    matched = _keyword_signals([events_text, alerts])
    # ... while signals found in RAG documents only count when those documents
    # actually belong to this incident's service (no cross-incident leakage).
    rag_matched = _keyword_signals([retrieved_text])
    service_relevant = _services_relate(
        incident.service,
        [c.metadata.get("service") for c in retrieved],
    )
    if service_relevant:
        matched.extend(m for m in rag_matched if m not in matched)

    k8s = _k8s_summary(retrieved) if retrieved else {"retrieved_documents": 0}
    degraded = bool(matched)

    if retrieved:
        if degraded:
            finding = (
                f"Pod/event signals detected in retrieved model-data k8s data: "
                f"{', '.join(k8s.get('event_signals', [])[:5])}."
            )
        elif not service_relevant:
            finding = (
                f"Retrieved {len(retrieved)} model k8s document(s) but none belong "
                f"to service '{incident.service}' "
                f"(found services={sorted({str(c.metadata.get('service')) for c in retrieved})[:6]}); "
                "treating cluster state for this incident as unknown."
            )
        else:
            finding = (
                f"Retrieved {len(retrieved)} model k8s document(s) "
                f"(namespaces={k8s.get('namespaces')}) but no degradation signals "
                "matched; cluster appears healthy for this incident."
            )
        severity = "medium" if degraded else "info"
    else:
        finding = (
            f"K8s RAG collection unavailable ({retrieval_error}) - no grounded "
            "model kubernetes evidence to analyze."
        )
        severity = "info"

    evidence = Evidence(
        evidence_id="ev-k8s-1",
        source="kubernetes",
        finding=finding,
        severity=severity,
        raw_data={
            "pod_statuses": [],
            "retrieved_documents": k8s.get("retrieved_documents", 0),
            "namespaces": k8s.get("namespaces", []),
            "services": k8s.get("services", []),
            "event_signals": k8s.get("event_signals", [])[:10],
            "degraded": degraded,
            "matched_signals": matched[:10],
        },
    )
    hypothesis = Hypothesis(
        hypothesis_id="hyp-k8s-1",
        description=f"Kubernetes analysis indicates: {finding}",
        confidence=0.6 if degraded else 0.3,
        supporting_evidence=["ev-k8s-1"],
        contradicting_evidence=[],
        label=HypothesisLabel.LIKELY if degraded else HypothesisLabel.POSSIBLE,
    ) if degraded else None
    return KubernetesAnalysisResult(
        evidence=[evidence],
        hypotheses=[hypothesis] if hypothesis else [],
        summary=finding,
    )


async def analyze_kubernetes_with_fallback(
    incident: Incident,
    classification: Optional[ClassificationResult] = None,
    llm=None,
) -> KubernetesAnalysisResult:
    """Always execute Kubernetes analysis. Uses LLM when available, else deterministic fallback.

    This is the entry point used by the orchestrator to ensure the subagent
    genuinely executes in every mode.
    """
    subagent_entry(AGENT_NAME, f"incident={incident.incident_id} llm_backed={llm is not None}")
    try:
        if llm is not None:
            try:
                result = await analyze_kubernetes(incident, classification)
            except Exception as exc:
                logger.warning(
                    "[kubernetes.agent] LLM analysis failed (%s: %s); using deterministic fallback",
                    type(exc).__name__,
                    exc,
                )
                subagent_error(AGENT_NAME, exc, "LLM failed, falling back to deterministic")
                result = _deterministic_analysis(incident)
        else:
            result = _deterministic_analysis(incident)
        degraded = bool(result.hypotheses)
        subagent_output(AGENT_NAME, f"severity={'medium' if degraded else 'info'} evidence_count={len(result.evidence)}")
    except Exception as exc:
        subagent_error(AGENT_NAME, exc)
        raise
    finally:
        subagent_exit(AGENT_NAME)
    return result


class KubernetesAgent:
    """Backward-compatible class wrapper around :func:`analyze_kubernetes`.

    Restored after commit c584fa0 replaced the original class with a
    function-based structured agent; ``app.agents.investigation.orchestrator``
    (and any other callers) still expect ``KubernetesAgent(llm, tool).run(...)``.
    """

    def __init__(self, llm=None, mock_tool: MockKubernetesTool | None = None):
        self.llm = llm
        self.mock_tool = mock_tool

    async def run(
        self,
        incident: Incident,
        classification: Optional[ClassificationResult] = None,
    ) -> KubernetesAnalysisResult:
        return await analyze_kubernetes(incident, classification)
