import os
from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.base import BaseAgent
from app.domain.models.incident import Incident
from app.tools.mock.logs import MockLogTool
from app.agents.investigation.log_analysis.prompt import build_log_analysis_prompt
from app.agents.investigation.log_analysis.parser import LogAnalysisResult, parse_log_analysis_response
from app.utils.logger import get_logger

logger = get_logger(__name__)

class LogAnalysisAgent(BaseAgent):
    """
    Agent responsible for analyzing application and system logs.
    """
    
    def __init__(self, llm: BaseChatModel, mock_log_tool: MockLogTool):
        # Resolve prompt path relative to this file to avoid working directory issues
        current_dir = os.path.dirname(os.path.abspath(__file__))
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        prompt_path = os.path.join(app_dir, "prompts", "templates", "log_analysis.txt")
        
        super().__init__(llm=llm, prompt_template_path=prompt_path)
        self.mock_log_tool = mock_log_tool
        
    async def run(self, incident: Incident) -> LogAnalysisResult:
        logger.info(f"LogAnalysisAgent starting for incident {incident.incident_id}")
        
        # 1. Build tool input
        tool_input = {
            "service": incident.service,
            "incident_type": incident.incident_type.value if hasattr(incident, 'incident_type') else "UNKNOWN",
            "environment": incident.environment.value
        }
        
        # 2. Fetch logs
        logger.info(f"Fetching logs for service {incident.service}")
        logs_output = await self.mock_log_tool.run(tool_input)
        
        if logs_output.error_count == 0 and logs_output.total_entries == 0:
            logger.info("No logs found.")
            return LogAnalysisResult(
                evidence=[],
                hypotheses=[],
                summary="No logs were found for the specified service and time range."
            )
            
        # 3. Build prompt
        template = self._load_prompt_template()
        human_prompt = build_log_analysis_prompt(template, incident, logs_output)
        
        # 4. Invoke LLM
        messages = self._build_messages(human_prompt)
        raw_response = await self._invoke_llm(messages)
        
        # 5. Parse and return
        result = parse_log_analysis_response(raw_response)
        
        logger.info(f"LogAnalysisAgent finished. Found {len(result.evidence)} evidence items and {len(result.hypotheses)} hypotheses.")
        return result
