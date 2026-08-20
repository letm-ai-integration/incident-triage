"""Deterministic confidence ceiling for the RCA & Report Agent.

Mirrors app/rules/classification.py's priority-floor pattern, but inverted:
priority has a floor because the risk there is complacency (rating something
less urgent than it is), whereas RCA confidence has a ceiling because the
risk is overconfidence (asserting a root cause more certain than the
underlying evidence supports). The LLM's stated confidence_score may be
lower than this ceiling but must never exceed it.
"""
from __future__ import annotations

from app.domain.models.hypothesis import Hypothesis, HypothesisLabel

_LABEL_WEIGHT = {
    HypothesisLabel.LIKELY: 1.0,
    HypothesisLabel.POSSIBLE: 0.6,
    HypothesisLabel.UNLIKELY: 0.25,
}


def compute_confidence_ceiling(hypotheses: list[Hypothesis]) -> float:
    """Ceiling on RCA confidence given only the hypotheses' own labels/scores.

    With no hypotheses at all, there is no basis for any confidence. Otherwise
    the ceiling is the strongest single hypothesis's own confidence, scaled by
    its label weight -- a hypothesis labeled UNLIKELY can't anchor a high
    confidence root-cause claim even if its raw score is high.
    """
    if not hypotheses:
        return 0.0
    return max(h.confidence * _LABEL_WEIGHT[h.label] for h in hypotheses)
