import asyncio
from datetime import datetime, timezone
from pydantic import BaseModel

class MockKubernetesToolOutput(BaseModel):
    service: str
    namespace: str
    pod_statuses: list[str]
    recent_events: list[str]
    resource_usage: dict

class MockKubernetesTool:
    """Mock tool to fetch Kubernetes pod status, events, and metrics."""
    
    async def run(self, incident_type: str, service: str, namespace: str = "default") -> MockKubernetesToolOutput:
        """Fetch simulated telemetry from mock Kubernetes cluster."""
        # Simulate network latency
        await asyncio.sleep(0.5)
        
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        if incident_type == "KUBERNETES":
            pod_statuses = ["CrashLoopBackOff", "Running", "ImagePullBackOff"]
            events = [
                f"[{now}] Warning: Back-off restarting failed container",
                f"[{now}] Normal: Pulled image 'registry/service:latest'",
                f"[{now}] Warning: Failed to pull image 'registry/service:latest': rpc error: code = Unknown desc = Error response from daemon"
            ]
            resources = {"cpu_usage_mcores": 1500, "memory_usage_mb": 2048, "cpu_limit_mcores": 2000, "memory_limit_mb": 2048}
        elif incident_type == "APPLICATION":
            pod_statuses = ["Running", "Running", "Running"]
            events = [
                f"[{now}] Normal: Sandbox changed",
                f"[{now}] Normal: Started container"
            ]
            resources = {"cpu_usage_mcores": 1800, "memory_usage_mb": 1024, "cpu_limit_mcores": 2000, "memory_limit_mb": 2048}
        else:
            pod_statuses = ["Running"]
            events = [
                f"[{now}] Normal: Created pod",
                f"[{now}] Normal: Started container"
            ]
            resources = {"cpu_usage_mcores": 100, "memory_usage_mb": 256, "cpu_limit_mcores": 500, "memory_limit_mb": 512}
            
        return MockKubernetesToolOutput(
            service=service,
            namespace=namespace,
            pod_statuses=pod_statuses,
            recent_events=events,
            resource_usage=resources
        )
