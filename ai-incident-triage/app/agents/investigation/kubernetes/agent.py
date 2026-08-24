from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from app.domain.models.incident import Incident
from app.tools.mock.kubernetes import MockKubernetesTool
from app.agents.investigation.kubernetes.prompt import build_kubernetes_prompt
from app.agents.investigation.kubernetes.parser import parse_kubernetes_response, KubernetesAnalysisResult

class KubernetesAgent:
    """Agent responsible for analyzing Kubernetes cluster state."""

    def __init__(self, llm: BaseChatModel, mock_k8s_tool: MockKubernetesTool):
        self.llm = llm
        self.mock_k8s_tool = mock_k8s_tool

    async def run(self, incident: Incident) -> KubernetesAnalysisResult:
        # 1. Fetch Kubernetes Telemetry
        incident_type = incident.tags[0] if incident.tags else "UNKNOWN"
        tool_output = await self.mock_k8s_tool.run(
            incident_type=incident_type,
            service=incident.service
        )
        
        # 2. Build prompt
        prompt_text = build_kubernetes_prompt(incident, tool_output)
        
        # 3. Invoke LLM
        response = await self.llm.ainvoke([HumanMessage(content=prompt_text)])
        
        # 4. Parse response
        result = parse_kubernetes_response(str(response.content))
        
        return result
