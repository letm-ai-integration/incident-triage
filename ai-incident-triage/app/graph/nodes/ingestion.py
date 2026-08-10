"""Ingestion node: normalize the raw incident payload."""

from __future__ import annotations

from app.dependencies import get_dependencies
from app.schemas.graph_state import IncidentTriageState


async def ingestion_node(state: IncidentTriageState) -> dict:
    deps = get_dependencies()
    incident = deps.ingestion_service.normalize(dict(state.get("incident") or {}))
    return {"incident": incident}
