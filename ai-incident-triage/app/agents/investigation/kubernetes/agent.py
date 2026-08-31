"""Kubernetes Agent: analyze mock K8s data, events & resources."""
from __future__ import annotations

import logging
from typing import Optional

from app.agents.investigation.kubernetes.parser import KubernetesAnalysisResult, parse_kubernetes_response
from app.agents.investigation.kubernetes.prompt import build_kubernetes_prompt
from app.domain.models.classification import ClassificationResult
from app.domain.models.incident import Incident
from app.guardrails.prompt_injection import check_prompt_injection
from app.llm.client import create_structured_agent
from app.tools.mock.kubernetes import MockKubernetesTool

import pathlib
SYSTEM_PROMPT_PATH = pathlib.Path(__file__).parent.parent.parent.parent / "prompts" / "templates" / "kubernetes.txt"
with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

logger = logging.getLogger(__name__)


async def analyze_kubernetes(
    incident: Incident,
    classification: Optional[ClassificationResult] = None,
    model: str | None = None,
) -> KubernetesAnalysisResult:
    """Analyze Kubernetes telemetry for the given incident."""
    logger.info("[kubernetes.agent] starting analysis incident=%s", incident.incident_id)

    # 1. Fetch Kubernetes Telemetry
    mock_k8s_tool = MockKubernetesTool()
    tool_output = await mock_k8s_tool.run(
        incident_type=classification.incident_type.value if classification else "APPLICATION",
        service=incident.service
    )

    # 2. Build user prompt
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
    logger.info("[kubernetes.agent] completed summary=%r", result.summary[:120])
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
