from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from app.domain.models.incident import Incident
from app.tools.mock.logs import MockLogTool
from app.agents.investigation.log_analysis.prompt import build_log_analysis_prompt
from app.agents.investigation.log_analysis.parser import parse_log_analysis_response, LogAnalysisResult

class LogAnalysisAgent:
    """Agent responsible for analyzing application and system logs."""

    def __init__(self, llm: BaseChatModel, mock_log_tool: MockLogTool):
        self.llm = llm
        self.mock_log_tool = mock_log_tool

    async def run(self, incident: Incident) -> LogAnalysisResult:
        # 1. Fetch logs
        incident_type = incident.tags[0] if incident.tags else "UNKNOWN"
        tool_output = await self.mock_log_tool.run(
            incident_type=incident_type,
            service=incident.service
        )
        logs_text = "\n".join(tool_output.logs)
        
        # 2. Build prompt
        prompt_text = build_log_analysis_prompt(incident, logs_text)
        
        # 3. Invoke LLM
        response = await self.llm.ainvoke([HumanMessage(content=prompt_text)])
        
        # 4. Parse response
        result = parse_log_analysis_response(str(response.content))
        
        return result
