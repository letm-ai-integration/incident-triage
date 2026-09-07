from enum import Enum


class EvidenceProvenance(str, Enum):
    """Where a piece of evidence/claim actually came from -- the grounding model.

    Ranked by how much independent verification backs the claim:

    - OBSERVED: directly supported by raw telemetry (logs, metrics, traces,
      or Kubernetes state/events) that we actually had access to.
    - REPORTED: supplied by the incident/alert description or an upstream source
      system; not independently verified against telemetry.
    - CONTEXT: retrieved from a runbook/knowledge base. Useful for remediation
      guidance, never proof that the symptom occurred.
    - INFERRED: a conclusion derived by reasoning over other evidence, never a
      raw observation.
    """
    OBSERVED = "OBSERVED"
    REPORTED = "REPORTED"
    CONTEXT = "CONTEXT"
    INFERRED = "INFERRED"