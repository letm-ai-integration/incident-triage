from pathlib import Path
from app.domain.models.incident import Incident

def build_log_analysis_prompt(incident: Incident, logs: str) -> str:
    """Build the prompt for log analysis."""
    template_path = Path(__file__).parent.parent.parent.parent / "prompts" / "templates" / "log_analysis.txt"
    
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
        
    prompt = template.format(
        incident_description=incident.description,
        incident_service=incident.service,
        incident_environment=str(incident.environment),
        logs=logs
    )
    return prompt
