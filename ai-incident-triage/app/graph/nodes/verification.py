# v3: verifies the resolution against observable recovery evidence.
#
# Phase 4: RESOLVED requires explicit, externally-supplied recovery telemetry;
# high RCA confidence alone never resolves (see
# app/services/verification_service.py for the full gate). Unresolved results
# route back to investigation (retry loop, bounded by retry_count <=
# domain.constants.MAX_INVESTIGATION_RETRIES); resolved results route to
# notification (see router.route_after_verification). The node also keeps the
# ``IncidentReport.verification`` field in sync via ``model_copy``.
from __future__ import annotations

from typing import Optional

from langchain_core.runnables import RunnableConfig

from app.graph.builder import get_deps
from app.graph.state import IncidentState
from app.services.verification_service import verification_service


def verification_node(state: IncidentState, config: Optional[RunnableConfig] = None) -> dict:
    """Verify the resolution and write the ``VerificationResult`` to state."""
    deps = get_deps(config)
    service = deps.get("verification_service", verification_service)
    try:
        update = service(state, deps)
    except Exception as exc:
        update = {"errors": state.get("errors", []) + [f"verification failed: {exc}"]}
    update.setdefault("current_step", "verification")
    return update