"""Kubernetes Agent: analyze mock K8s data, events & resources."""
from __future__ import annotations

from typing import Any

from app.agents.investigation.kubernetes.parser import KubernetesAnalysisResult, parse_kubernetes_response
from app.agents.investigation.kubernetes.prompt import build_kubernetes_prompt
from app.domain.models.classification import ClassificationResult
from app.domain.models.incident import Incident
from app.llm.client import create_structured_agent
from app.tools.mock.kubernetes import MockKubernetesTool

import pathlib
SYSTEM_PROMPT_PATH = pathlib.Path(__file__).parent.parent.parent.parent / "prompts" / "templates" / "kubernetes.txt"
with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

async def analyze_kubernetes(
    incident: Incident, classification: ClassificationResult, model: str | None = None
) -> KubernetesAnalysisResult:
    """Analyze Kubernetes telemetry for the given incident."""
    
    # 1. Fetch Kubernetes Telemetry
    mock_k8s_tool = MockKubernetesTool()
    tool_output = await mock_k8s_tool.run(
        incident_type=classification.incident_type.value,
        service=incident.service
    )
    
    # 2. Build user prompt
    user_prompt = build_kubernetes_prompt(incident, tool_output)
    
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
    return parse_kubernetes_response(response)
