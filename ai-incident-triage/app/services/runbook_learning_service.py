"""
Service for the Runbook Learning Loop.

Automatically updates or creates runbook documentation from successfully resolved
incidents, closing the feedback loop so the system improves over time.
"""
from __future__ import annotations

import logging
import datetime
from pathlib import Path

from app.config import get_settings
from app.graph.state import IncidentState
from app.knowledge.retriever import retrieve
from app.knowledge.vector_store import VectorStoreCollectionMissing
from app.knowledge.ingest import ingest_file_into_collection
from app.llm.client import chat_completion

logger = logging.getLogger(__name__)

RUNBOOKS_DIR = Path("knowledge_base/runbooks")


def run_runbook_learning_loop(state: dict) -> dict:
    """Execute the runbook learning loop and return state updates."""
    # Ensure the incident was resolved
    verification = state.get("verification_result")
    if not verification or not verification.is_resolved:
        logger.info("[runbook_learning] Incident not resolved, skipping learning.")
        return {"runbook_learning_attempted": False}

    report = state.get("incident_report")
    if not report:
        logger.warning("[runbook_learning] No incident report found, skipping learning.")
        return {"runbook_learning_attempted": False}

    incident = state.get("incident")
    classification = report.classification
    rca = report.root_cause

    if not incident or not classification or not rca:
        logger.warning("[runbook_learning] Missing critical state data, skipping learning.")
        return {"runbook_learning_attempted": False}

    try:
        # 1. Similarity check
        query_text = f"incident type: {classification.incident_type.value} priority: {classification.priority.value} cause: {rca.primary_cause.description}"
        try:
            results = retrieve(collection="runbooks", query_text=query_text, k=1)
        except VectorStoreCollectionMissing:
            results = []

        threshold = get_settings().runbook_update_similarity_threshold

        file_touched = ""
        score = 0.0

        if results and results[0].score >= threshold:
            # 2a. Update existing runbook
            match = results[0]
            score = match.score
            source_file = match.metadata.get("source_file")
            
            if source_file and Path(source_file).exists():
                _append_to_runbook(source_file, incident.incident_id, classification, rca, verification)
                file_touched = source_file
            else:
                logger.error("[runbook_learning] Matched runbook file not found on disk.")
                return {"runbook_learning_attempted": False}
        else:
            # 2b. Create new runbook
            score = results[0].score if results else 0.0
            file_touched = _create_new_runbook(incident, classification, rca, verification, report)

        # 3. Re-ingest into vector store
        if file_touched:
            ingest_file_into_collection(file_touched, "runbooks")

        logger.info(f"[runbook_learning] Successfully processed {file_touched} with score {score:.2f}")
        return {
            "runbook_learning_attempted": True,
            "runbook_learning_file_touched": file_touched,
            "runbook_learning_similarity_score": score,
        }

    except Exception as exc:
        logger.error(f"[runbook_learning] Learning loop failed: {exc}")
        return {"runbook_learning_attempted": False}


def _append_to_runbook(file_path: str, incident_id: str, classification, rca, verification) -> None:
    """Append a new 'Observed Incident' section to an existing runbook."""
    date_str = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")
    
    append_content = f"""

## Observed Incident — {date_str} — {incident_id}

**Severity:** {classification.priority.value}
**Root Cause:** {rca.primary_cause.description}
**Resolution Evidence:** {verification.resolution_evidence or 'N/A'}
"""
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(append_content)


def _create_new_runbook(incident, classification, rca, verification, report) -> str:
    """Use the LLM to synthesize a new runbook markdown file."""
    prompt = f"""
You are an expert SRE. Create a new incident runbook in Markdown based on a recently resolved incident.
Do not output anything except the exact Markdown file contents.

The file MUST start with YAML frontmatter containing:
---
title: <A concise descriptive title>
service: {incident.service}
severity_applicable: [{classification.priority.value}]
tags: {classification.affected_services or ['incident']}
version: 1
last_reviewed: {datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")}
owning_team: auto-generated
---

After the frontmatter, provide the runbook content following this structure:
# <Title>

## Symptoms
<Describe the symptoms based on the alert and data>

## Diagnosis Steps
<Provide logical steps to diagnose this, based on how the root cause was identified>

## Resolution
<Describe how to fix it>

## Observed Incident — {datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")} — {incident.incident_id}
**Severity:** {classification.priority.value}
**Root Cause:** {rca.primary_cause.description}
**Resolution Evidence:** {verification.resolution_evidence or 'N/A'}

---
INPUT DATA:
Alert Title: {incident.title}
Alert Description: {incident.description}
Root Cause: {rca.primary_cause.description}
Recommended Actions: {', '.join(report.recommended_actions)}
"""
    
    # Use deterministic fallback model or active chat model
    from app.llm.client import chat_completion
    response = chat_completion([{"role": "user", "content": prompt}])
    
    content = str(response.choices[0].message.content).strip()
    if content.startswith("```markdown"):
        content = content[11:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    
    # Generate filename
    import re
    safe_title = re.sub(r'[^a-z0-9]+', '-', incident.title.lower()).strip('-')
    if not safe_title:
        safe_title = incident.incident_id.lower()
    
    RUNBOOKS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = str(RUNBOOKS_DIR / f"{safe_title}.md")
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    return file_path
