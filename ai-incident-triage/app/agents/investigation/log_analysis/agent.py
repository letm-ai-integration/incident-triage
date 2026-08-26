"""Log Analysis Agent: analyze mock logs and find errors."""
from __future__ import annotations

import logging
import pathlib
from typing import Optional

from app.agents.investigation.log_analysis.parser import LogAnalysisResult, parse_log_analysis_response
from app.agents.investigation.log_analysis.prompt import build_log_analysis_prompt
from app.domain.models.classification import ClassificationResult
from app.domain.models.incident import Incident
from app.llm.client import create_structured_agent
from app.tools.mock.logs import MockLogTool

SYSTEM_PROMPT_PATH = pathlib.Path(__file__).parent.parent.parent.parent / "prompts" / "templates" / "log_analysis.txt"
with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

logger = logging.getLogger(__name__)


async def analyze_logs(
    incident: Incident,
    classification: Optional[ClassificationResult] = None,
    model: str | None = None,
) -> LogAnalysisResult:
    """Analyze application and system logs for the given incident."""
    logger.info("[log_analysis.agent] starting analysis incident=%s", incident.incident_id)

    # 1. Fetch logs
    mock_log_tool = MockLogTool()
    tool_output = await mock_log_tool.run(
        incident_type=classification.incident_type.value if classification else "APPLICATION",
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
    result = parse_log_analysis_response(response)
    logger.info("[log_analysis.agent] completed summary=%r", result.summary[:120])
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
