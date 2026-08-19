import asyncio
from datetime import datetime, timezone
from pydantic import BaseModel

class MockLogToolOutput(BaseModel):
    service: str
    logs: list[str]

class MockLogTool:
    """Mock tool to fetch application and system logs."""
    
    async def run(self, incident_type: str, service: str, time_range: str = "last 1h") -> MockLogToolOutput:
        """Fetch logs from mock log system."""
        # Simulate network latency
        await asyncio.sleep(0.5)
        
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        if incident_type == "APPLICATION":
            logs = [
                f"[{now}] INFO [{service}] Service started successfully.",
                f"[{now}] ERROR [{service}] Exception processing request: Connection timeout to backend API.",
                f"[{now}] ERROR [{service}] NullPointerException at app.handlers.Process(Process.java:42)",
                f"[{now}] WARN [{service}] Retry attempt 1 failed.",
                f"[{now}] ERROR [{service}] Exception processing request: Connection timeout to backend API."
            ]
        elif incident_type == "DATABASE":
            logs = [
                f"[{now}] INFO [{service}] DB Connection pool initialized.",
                f"[{now}] ERROR [{service}] FATAL: remaining connection slots are reserved for non-replication superuser connections",
                f"[{now}] ERROR [{service}] FATAL: terminating connection due to administrator command",
                f"[{now}] WARN [{service}] connection pool exhausted"
            ]
        elif incident_type == "KUBERNETES":
            logs = [
                f"[{now}] INFO [kubelet] Pod sandbox created.",
                f"[{now}] ERROR [kubelet] Failed to pull image 'registry/service:latest': rpc error: code = Unknown desc = Error response from daemon",
                f"[{now}] WARN [kubelet] Back-off pulling image 'registry/service:latest'"
            ]
        else:
            logs = [
                f"[{now}] INFO [{service}] Received incoming request.",
                f"[{now}] ERROR [{service}] Unexpected error occurred. Code: 500.",
                f"[{now}] INFO [{service}] Finished processing request."
            ]
            
        return MockLogToolOutput(service=service, logs=logs)
