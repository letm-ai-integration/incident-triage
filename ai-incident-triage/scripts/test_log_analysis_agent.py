import asyncio
import json
from app.config import get_settings
from app.tools.mock.logs import MockLogTool
from app.agents.investigation.log_analysis.agent import LogAnalysisAgent
from app.domain.models.incident import Incident
from app.domain.enums import Environment, Priority, IncidentType
from datetime import datetime
from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import AIMessage

async def main():
    settings = get_settings()
    
    # We use a FakeListChatModel instead of LLMFactory to bypass the need for a Groq API key in tests
    mock_llm_response = json.dumps({
        "evidence": [
            {
                "evidence_id": "LOG-001",
                "source": "log_analysis",
                "finding": "Found 5 instances of java.sql.SQLTimeoutException in payment-api logs.",
                "severity": "HIGH",
                "raw_data": {"log_message": "Timeout trying to connect to DB at db-primary.internal:5432"}
            }
        ],
        "hypotheses": [
            {
                "hypothesis_id": "HYP-001",
                "description": "Database connection pool is exhausted due to high latency queries.",
                "confidence": 0.85,
                "supporting_evidence": ["LOG-001"],
                "contradicting_evidence": [],
                "label": "LIKELY"
            }
        ],
        "summary": "Log analysis identified severe database connection timeouts."
    })
    
    llm = FakeListChatModel(responses=[mock_llm_response])
    
    tool = MockLogTool()
    agent = LogAnalysisAgent(llm=llm, mock_log_tool=tool)

    incident = Incident(
        incident_id="TEST-001",
        title="Database connection timeout in payment-api",
        description="Payment API returning 500 errors due to database connection timeouts",
        source="manual",
        service="payment-api",
        environment=Environment.PRODUCTION,
        priority_hint=Priority.P2,
        timestamp=datetime.now(),
    )
    
    # Removed invalid incident.incident_type assignment 
    # Mock Log tool will infer DB scenario from "db" in service name
    incident.service = "payment-api-db"

    print("Running Log Analysis Agent with Mock LLM...")
    result = await agent.run(incident)
    
    print("\n--- RESULTS ---")
    print(f"Summary: {result.summary}")
    
    print(f"\nEvidence items: {len(result.evidence)}")
    for e in result.evidence:
        print(f"  [{e.severity}] {e.finding}")
        
    print(f"\nHypotheses: {len(result.hypotheses)}")
    for h in result.hypotheses:
        print(f"  [{h.label.value}] {h.description} (confidence: {h.confidence})")

if __name__ == "__main__":
    asyncio.run(main())
