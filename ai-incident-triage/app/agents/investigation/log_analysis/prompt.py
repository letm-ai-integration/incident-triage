import json
from app.domain.models.incident import Incident
from app.schemas.tool_outputs import LogAnalysisToolOutput

def build_log_analysis_prompt(template: str, incident: Incident, logs: LogAnalysisToolOutput) -> str:
    """
    Injects incident and log data into the log analysis prompt template.
    """
    # Serialize data
    incident_data = json.dumps({
        "incident_id": incident.incident_id,
        "title": incident.title,
        "description": incident.description,
        "service": incident.service,
        "environment": incident.environment.value,
        "timestamp": incident.timestamp.isoformat()
    }, indent=2)
    
    # Serialize logs
    log_data = json.dumps([
        {
            "timestamp": log.timestamp,
            "level": log.level,
            "service": log.service,
            "message": log.message,
            "stack_trace": log.stack_trace
        }
        for log in logs.logs
    ], indent=2)
    
    # Inject into template
    prompt = template.replace("{incident_data}", incident_data)
    prompt = prompt.replace("{log_data}", log_data)
    
    return prompt
