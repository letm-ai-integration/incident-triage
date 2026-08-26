import json
from app.domain.models.incident import Incident

def build_log_analysis_prompt(incident: Incident, logs: str) -> str:
    """Build the user prompt data payload for the Log Analysis agent."""
    incident_data = {
        "title": incident.title,
        "description": incident.description,
        "service": incident.service,
        "environment": str(incident.environment),
        "tags": incident.tags,
    }

    prompt = f"""=== INCIDENT DATA ===
{json.dumps(incident_data, indent=2)}

=== LOGS ===
{logs}
"""
    return prompt
