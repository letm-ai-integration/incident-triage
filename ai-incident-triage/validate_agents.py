import asyncio
import json
import os
from pathlib import Path

from app.domain.models.incident import Incident
from app.agents.investigation.kubernetes.agent import analyze_kubernetes
from app.agents.investigation.log_analysis.agent import analyze_logs
from app.agents.classification.agent import classify_incident
from app.agents.investigation.runbook.agent import run_runbook_agent

async def main():
    print("=======================================")
    print("       VALIDATING AGENTS LOCALLY       ")
    print("=======================================")

    # 1. Load mock incident
    incident_path = Path("data/incidents/crashloopbackoff.json")
    with open(incident_path, "r") as f:
        data = json.load(f)
        
    incident = Incident(**data)
    print(f"Loaded Incident: {incident.title}")

    # 2. Test Classification Agent
    print("\n--- Triggering ClassificationAgent ---")
    try:
        classification_result = classify_incident(incident)
        print(f"Classification: {classification_result.incident_type.value}, Priority: {classification_result.priority.value}")
        print(f"Reasoning: {classification_result.reasoning}")
    except Exception as e:
        print(f"ClassificationAgent failed: {e}")
        return

    # 3. Test LogAnalysis Agent
    print("\n--- Triggering LogAnalysisAgent ---")
    try:
        log_result = await analyze_logs(incident, classification_result)
        print(f"Summary: {log_result.summary}")
        for ev in log_result.evidence:
            print(f" Evidence: {ev.finding}")
        for hyp in log_result.hypotheses:
            print(f" Hypothesis: {hyp.description} (Confidence: {hyp.confidence})")
    except Exception as e:
        print(f"LogAnalysisAgent failed: {e}")

    # 4. Test Kubernetes Agent
    print("\n--- Triggering KubernetesAgent ---")
    try:
        k8s_result = await analyze_kubernetes(incident, classification_result)
        print(f"Summary: {k8s_result.summary}")
        for ev in k8s_result.evidence:
            print(f" Evidence: {ev.finding}")
        for hyp in k8s_result.hypotheses:
            print(f" Hypothesis: {hyp.description} (Confidence: {hyp.confidence})")
    except Exception as e:
        print(f"KubernetesAgent failed: {e}")

    # 5. Test Runbook Agent
    print("\n--- Triggering RunbookAgent ---")
    try:
        rb_result = run_runbook_agent(data, classification_result)
        print(f"Status: {rb_result.status.value}")
        if rb_result.matched_title:
            print(f"Matched Runbook: {rb_result.matched_title}")
    except Exception as e:
        print(f"RunbookAgent failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
