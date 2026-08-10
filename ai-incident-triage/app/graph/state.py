"""Re-export of the graph state contract.

The authoritative definition lives in :mod:`app.schemas.graph_state`; this
module exists so graph code can import it from ``app.graph.state``.
"""

from app.schemas.graph_state import IncidentTriageState

__all__ = ["IncidentTriageState"]
