import asyncio

from app.agents.base import BaseAgent
from app.agents.investigation.kubernetes import KubernetesAgent
from app.agents.investigation.log_analysis import LogAnalysisAgent
from app.agents.investigation.runbook import RunbookAgent
from app.domain.models import (
    Evidence,
    Hypothesis,
    Incident,
    InvestigationSummary,
)


class InvestigationOrchestrator(BaseAgent[Incident, InvestigationSummary]):
    """Runs the parallel investigation sub-agents and consolidates findings.

    Each sub-agent returns ``(evidence, hypotheses)``. The orchestrator merges
    them into a single :class:`InvestigationSummary`.
    """

    name = "investigation"

    def __init__(
        self,
        log_analysis: LogAnalysisAgent | None = None,
        runbook: RunbookAgent | None = None,
        kubernetes: KubernetesAgent | None = None,
    ) -> None:
        self._log_analysis = log_analysis or LogAnalysisAgent()
        self._runbook = runbook or RunbookAgent()
        self._kubernetes = kubernetes or KubernetesAgent()

    async def run(self, incident: Incident) -> InvestigationSummary:
        results = list(
            await asyncio.gather(
                self._log_analysis.run(incident),
                self._runbook.run(incident),
                self._kubernetes.run(incident),
            )
        )
        return self._consolidate(results, incident)

    def _consolidate(
        self,
        results: list[tuple[list[Evidence], list[Hypothesis]]],
        incident: Incident,
    ) -> InvestigationSummary:
        evidence: list[Evidence] = []
        hypotheses: list[Hypothesis] = []
        for ev, hy in results:
            evidence.extend(ev)
            hypotheses.extend(hy)
        summary = (
            f"Investigated incident '{incident.title}' across "
            f"{len(results)} sub-agents; collected {len(evidence)} evidence items "
            f"and {len(hypotheses)} hypotheses."
        )
        return InvestigationSummary(
            evidence=evidence,
            hypotheses=hypotheses,
            summary=summary,
        )
