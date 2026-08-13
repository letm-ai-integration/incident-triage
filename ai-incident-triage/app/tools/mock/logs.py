from datetime import datetime, timedelta
import random
from typing import Dict, Any

from app.tools.base import BaseTool
from app.schemas.tool_outputs import LogAnalysisToolOutput, LogEntry

class MockLogTool(BaseTool):
    """
    Retrieves simulated application and system logs for a given service and time range.
    """
    
    @property
    def name(self) -> str:
        return "mock_log_retriever"
        
    @property
    def description(self) -> str:
        return "Retrieves simulated application and system logs for a given service and time range"
        
    async def run(self, input_data: Dict[str, Any]) -> LogAnalysisToolOutput:
        service = input_data.get("service", "unknown-service")
        incident_type = input_data.get("incident_type", "UNKNOWN")
        environment = input_data.get("environment", "PRODUCTION")
        
        # Generate timestamps
        now = datetime.now()
        start_time = now - timedelta(minutes=30)
        
        logs = []
        error_count = 0
        
        # Determine scenario
        scenario = incident_type.upper()
        
        if scenario == "DATABASE" or "timeout" in service.lower() or "db" in service.lower():
            logs = self._generate_db_timeout_logs(service, environment, start_time)
        elif scenario == "KUBERNETES" or "pod" in service.lower():
            logs = self._generate_crashloop_logs(service, environment, start_time)
        elif scenario == "NETWORK" or "503" in service.lower():
            logs = self._generate_http_503_logs(service, environment, start_time)
        elif "image" in service.lower() or scenario == "INFRASTRUCTURE":
            logs = self._generate_image_pull_logs(service, environment, start_time)
        else:
            logs = self._generate_generic_logs(service, environment, start_time)
            
        error_count = sum(1 for log in logs if log.level == "ERROR")
            
        return LogAnalysisToolOutput(
            logs=logs,
            service=service,
            time_range=f"{start_time.isoformat()} to {now.isoformat()}",
            total_entries=len(logs),
            error_count=error_count
        )
        
    def _generate_db_timeout_logs(self, service: str, env: str, start: datetime) -> list[LogEntry]:
        logs = []
        for i in range(20):
            t = (start + timedelta(minutes=i*1.5)).isoformat()
            if i < 5:
                logs.append(LogEntry(timestamp=t, level="INFO", service=service, message="Handling request"))
            elif i < 10:
                logs.append(LogEntry(timestamp=t, level="WARN", service=service, message="Connection pool approaching limit (80%)"))
            elif i < 15:
                logs.append(LogEntry(timestamp=t, level="ERROR", service=service, message="Connection pool exhausted", stack_trace="java.sql.SQLTransientConnectionException: HikariPool-1 - Connection is not available, request timed out after 30000ms"))
            else:
                logs.append(LogEntry(timestamp=t, level="ERROR", service=service, message="Failed to connect to database", stack_trace="java.sql.SQLTimeoutException: Timeout trying to connect to DB at db-primary.internal:5432"))
        return logs

    def _generate_crashloop_logs(self, service: str, env: str, start: datetime) -> list[LogEntry]:
        logs = []
        for i in range(15):
            t = (start + timedelta(minutes=i*2)).isoformat()
            if i % 3 == 0:
                logs.append(LogEntry(timestamp=t, level="INFO", service=service, message="Starting application server"))
            elif i % 3 == 1:
                logs.append(LogEntry(timestamp=t, level="WARN", service=service, message="Memory usage critical (95%)"))
            else:
                logs.append(LogEntry(timestamp=t, level="ERROR", service=service, message="Process killed", stack_trace="OOMKilled: Container exited with code 137"))
        return logs

    def _generate_http_503_logs(self, service: str, env: str, start: datetime) -> list[LogEntry]:
        logs = []
        for i in range(18):
            t = (start + timedelta(minutes=i*1.5)).isoformat()
            if i < 8:
                logs.append(LogEntry(timestamp=t, level="INFO", service=service, message="Request processed successfully (200 OK)"))
            elif i < 12:
                logs.append(LogEntry(timestamp=t, level="WARN", service=service, message="Upstream latency degraded (>500ms)"))
            else:
                logs.append(LogEntry(timestamp=t, level="ERROR", service=service, message="Upstream connection timeout", stack_trace="Error 503 Service Unavailable: upstream server timeout / api-gateway"))
        return logs

    def _generate_image_pull_logs(self, service: str, env: str, start: datetime) -> list[LogEntry]:
        logs = []
        for i in range(10):
            t = (start + timedelta(minutes=i*3)).isoformat()
            if i < 3:
                logs.append(LogEntry(timestamp=t, level="INFO", service=service, message="Preparing to pull image"))
            else:
                logs.append(LogEntry(timestamp=t, level="ERROR", service=service, message="Failed to pull image", stack_trace="ErrImagePull: rpc error: code = Unknown desc = Error response from daemon: Get https://registry.internal/v2/: unauthorized: authentication required"))
        return logs
        
    def _generate_generic_logs(self, service: str, env: str, start: datetime) -> list[LogEntry]:
        logs = []
        for i in range(15):
            t = (start + timedelta(minutes=i*2)).isoformat()
            if i % 5 == 0:
                logs.append(LogEntry(timestamp=t, level="ERROR", service=service, message="Unexpected application error", stack_trace="Exception in thread \"main\" java.lang.NullPointerException\n\tat com.company.app.Main.process(Main.java:42)"))
            elif i % 5 == 1:
                logs.append(LogEntry(timestamp=t, level="WARN", service=service, message="Configuration deprecated or missing default fallback"))
            else:
                logs.append(LogEntry(timestamp=t, level="INFO", service=service, message="Healthcheck passed"))
        return logs
