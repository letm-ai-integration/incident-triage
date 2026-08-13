from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class LogEntry(BaseModel):
    timestamp: str
    level: str
    service: str
    message: str
    stack_trace: Optional[str] = None

class LogAnalysisToolOutput(BaseModel):
    logs: List[LogEntry] = Field(default_factory=list)
    service: str
    time_range: str
    total_entries: int = 0
    error_count: int = 0

class KubernetesAnalysisOutput(BaseModel):
    # TODO: Implement K8s tool output schema
    pass

class RunbookLookupOutput(BaseModel):
    # TODO: Implement Runbook RAG output schema
    pass

class MetricsOutput(BaseModel):
    # TODO: Implement Metrics tool output schema
    pass
