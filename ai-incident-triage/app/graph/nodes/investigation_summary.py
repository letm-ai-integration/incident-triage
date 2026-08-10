# v2: consolidates the evidence + hypotheses produced by the parallel
# investigation sub-agents into a single ``investigation_summary`` dict.
from __future__ import annotations

from typing import Optional

from langchain_core.runnables import RunnableConfig

from app.domain.models.hypothesis import Hypothesis
from app.graph.builder import get_deps
from app.graph.state import IncidentState


def investigation_summary_node(
    state: IncidentState, config: Optional[RunnableConfig] = None
) -> dict:
    """Summarize the investigation findings into ``investigation_summary``."""
    deps = get_deps(config)
    service = deps.get("investigation_summary_service", _default_investigation_summary)
    try:
        update = service(state, deps)
    except Exception as exc:
        update = {"errors": state.get("errors", []) + [f"investigation_summary failed: {exc}"]}
    update.setdefault("current_step", "investigation_summary")
    return update


def _default_investigation_summary(state: IncidentState, deps: dict) -> dict:
    """Fallback summary: count evidence/hypotheses and pick the top hypothesis."""
    evidence = state.get("evidence", [])
    hypotheses = state.get("hypotheses", [])
    top: Optional[Hypothesis] = max(hypotheses, key=lambda h: h.confidence) if hypotheses else None
    sources = sorted({item.source for item in evidence})
    return {
        "investigation_summary": {
            "summary": (
                f"Collected {len(evidence)} piece(s) of evidence from {sources} "
                f"and {len(hypotheses)} hypothesis(es)."
            ),
            "evidence_count": len(evidence),
            "hypothesis_count": len(hypotheses),
            "top_hypothesis_id": top.hypothesis_id if top else None,
            "sources": sources,
        }
    }
