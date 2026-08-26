"""Log Analysis Agent: analyze mock logs and find errors."""
from __future__ import annotations

import pathlib
from typing import Any

from app.agents.investigation.log_analysis.parser import LogAnalysisResult, parse_log_analysis_response
from app.agents.investigation.log_analysis.prompt import build_log_analysis_prompt
from app.domain.models.classification import ClassificationResult
from app.domain.models.incident import Incident
from app.llm.client import create_structured_agent
from app.tools.mock.logs import MockLogTool

SYSTEM_PROMPT_PATH = pathlib.Path(__file__).parent.parent.parent.parent / "prompts" / "templates" / "log_analysis.txt"
with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

async def analyze_logs(
    incident: Incident, classification: ClassificationResult, model: str | None = None
) -> LogAnalysisResult:
    """Analyze application and system logs for the given incident."""
    
    # 1. Fetch logs
    mock_log_tool = MockLogTool()
    tool_output = await mock_log_tool.run(
        incident_type=classification.incident_type.value,
        service=incident.service
    )
    logs_text = "\n".join(tool_output.logs)
    
    # 2. Build user prompt
    user_prompt = build_log_analysis_prompt(incident, logs_text)
    
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
    return parse_log_analysis_response(response)
