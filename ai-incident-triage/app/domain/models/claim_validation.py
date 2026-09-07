"""Deterministic claim-validation types (Phase 3).

A ``ClaimValidationFinding`` records one verifiable claim detected inside a
hypothesis, whether the available evidence supports it, and -- when it does
not -- the penalty the confidence calibration applies and the qualifier the
RCA must attach instead of presenting the claim as confirmed.
"""
from enum import Enum

from pydantic import BaseModel


class ClaimCategory(str, Enum):
    OOMKILLED = "oomkilled"
    CRASHLOOPBACKOFF = "crashloopbackoff"
    CPU_SATURATION = "cpu_saturation"
    DB_OUTAGE = "db_outage"
    RECOVERY = "recovery"
    RUNBOOK_ONLY = "runbook_only"
    EMPTY_SOURCE = "empty_source"


class ClaimValidationFinding(BaseModel):
    """One unsupported-or-qualified claim within a hypothesis.

    ``supported=False`` means the claim must not be presented as confirmed:
    either its wording is downgraded (``penalty=0`` reword cases such as
    "DB outage" with only pool-exhaustion evidence) or its confidence is
    reduced (``penalty>0``) and the ``qualifier`` wording is used instead.
    """

    hypothesis_id: str
    category: ClaimCategory
    claim: str = ""
    supported: bool = False
    penalty: float = 0.0
    qualifier: str = ""
    detail: str = ""