import json
from pathlib import Path
from app.domain.models.incident import Incident
from app.tools.mock.kubernetes import MockKubernetesToolOutput

def build_kubernetes_prompt(incident: Incident, k8s_data: MockKubernetesToolOutput) -> str:
    """Build the prompt for the Kubernetes investigation agent."""
    prompt_path = Path(__file__).parent.parent.parent.parent / "prompts" / "templates" / "kubernetes.txt"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        template = "Analyze the kubernetes data and output JSON." # Fallback

    incident_data = {
        "title": incident.title,
        "description": incident.description,
        "service": incident.service,
        "tags": incident.tags,
    }

    prompt = f"""{template}

=== INCIDENT DATA ===
{json.dumps(incident_data, indent=2)}

=== KUBERNETES TELEMETRY ===
Service: {k8s_data.service}
Namespace: {k8s_data.namespace}
Pod Statuses: {', '.join(k8s_data.pod_statuses)}
Resource Usage: {json.dumps(k8s_data.resource_usage, indent=2)}

Recent Events:
{chr(10).join(k8s_data.recent_events)}
"""
    return prompt
