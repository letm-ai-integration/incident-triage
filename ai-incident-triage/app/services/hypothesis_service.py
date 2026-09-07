"""Deterministic confidence calibration (Phase 3, second half).

Extends -- rather than replaces -- the existing confidence machinery: the
orchestrator's evidence-grounded heuristic (severity/independent-source
contributions) stays the primary confidence source, and app/rules/confidence.py
stays the shared ceiling used on the LLM path. This module applies the
downward-only adjustments from the claim-validation findings:

- an unsupported claim lowers the hypothesis's confidence and label;
- wording qualifiers ("reported ...", "not independently verified ...") are
  attached to the RCA so a downgraded claim is never presented as confirmed;
- the RCA confidence_score is capped by the deterministic ceiling.

Every adjustment is a reduction or a clarification -- nothing here can raise
confidence or invent new certainty.
"""
from __future__ import annotations

import logging

from app.domain.models.claim_validation import ClaimValidationFinding
from app.domain.models.hypothesis import Hypothesis, HypothesisLabel
from app.domain.models.root_cause import RootCauseAnalysis
from app.rules.confidence import compute_confidence_ceiling

logger = logging.getLogger(__name__)

# A single hypothesis is never penalized more than this total, so one
# multi-category claim can't zero a hypothesis on its own.
_MAX_PENALTY = 0.25


def _label_for(confidence: float) -> HypothesisLabel:
    if confidence >= 0.7:
        return HypothesisLabel.LIKELY
    if confidence >= 0.4:
        return HypothesisLabel.POSSIBLE
    return HypothesisLabel.UNLIKELY


def _penalty_for(hypothesis_id: str, findings: list[ClaimValidationFinding]) -> float:
    applicable = [
        f for f in findings
        if f.hypothesis_id == hypothesis_id and not f.supported and f.penalty > 0.0
    ]
    return min(_MAX_PENALTY, sum(f.penalty for f in applicable))


def calibrate_hypotheses(
    hypotheses: list[Hypothesis], findings: list[ClaimValidationFinding]
) -> list[Hypothesis]:
    """Return copies of ``hypotheses`` with unsupported-claim penalties applied.

    Confidence is only ever reduced; the label is recomputed from the reduced
    confidence so a downgraded claim can't keep a misleading LIKELY badge.
    """
    calibrated: list[Hypothesis] = []
    for h in hypotheses:
        delta = _penalty_for(h.hypothesis_id, findings)
        if not delta:
            calibrated.append(h)
            continue
        confidence = max(0.05, round(h.confidence - delta, 2))
        calibrated.append(
            h.model_copy(update={"confidence": confidence, "label": _label_for(confidence)})
        )
    return calibrated


def _qualifiers_for(
    hypothesis_id: str, findings: list[ClaimValidationFinding]
) -> list[str]:
    seen: list[str] = []
    for f in findings:
        if f.hypothesis_id != hypothesis_id or f.supported or not f.qualifier:
            continue
        if f.qualifier not in seen:
            seen.append(f.qualifier)
    return seen


def _append_qualifier(description: str, qualifiers: list[str]) -> str:
    if not qualifiers:
        return description
    joined = " ; ".join(qualifiers)
    if joined in description:
        return description
    return f"{description} ({joined})"


def finalize_root_cause(
    root_cause: RootCauseAnalysis,
    findings: list[ClaimValidationFinding],
    hypotheses: list[Hypothesis] | None = None,
) -> RootCauseAnalysis:
    """Apply validation penalties + wording to an RCA before it is reported.

    ``hypotheses`` (the investigation-stage hypotheses) is accepted for API
    symmetry but the ceiling is computed from the RCA itself, exactly as the
    LLM path does -- one shared definition of "how certain can this RCA be".
    """
    primary = root_cause.primary_cause
    delta = _penalty_for(primary.hypothesis_id, findings)
    if delta:
        confidence = max(0.05, round(primary.confidence - delta, 2))
        primary = primary.model_copy(
            update={"confidence": confidence, "label": _label_for(confidence)}
        )

    # Shared deterministic ceiling (app/rules/confidence.py) -- no competing
    # confidence calculator.
    ceiling = compute_confidence_ceiling([primary, *root_cause.contributing_factors])
    confidence_score = min(primary.confidence, ceiling)

    primary_desc = _append_qualifier(
        primary.description, _qualifiers_for(primary.hypothesis_id, findings)
    )
    if primary_desc != primary.description:
        primary = primary.model_copy(update={"description": primary_desc})

    factors = []
    for factor in root_cause.contributing_factors:
        desc = _append_qualifier(factor.description, _qualifiers_for(factor.hypothesis_id, findings))
        factors.append(factor.model_copy(update={"description": desc}) if desc != factor.description else factor)

    if delta:
        logger.info(
            "claim validation reduced primary-cause confidence %.2f -> %.2f (%s)",
            root_cause.primary_cause.confidence,
            primary.confidence,
            root_cause.primary_cause.hypothesis_id,
        )
    return root_cause.model_copy(
        update={
            "primary_cause": primary,
            "contributing_factors": factors,
            "confidence_score": round(confidence_score, 2),
            "claim_validation": findings,
        }
    )