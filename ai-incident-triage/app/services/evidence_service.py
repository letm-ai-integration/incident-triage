"""Deterministic claim validation (Phase 3, first half).

``validate_hypotheses`` inspects each hypothesis for the claim categories the
master instructions name (OOMKilled, CrashLoopBackOff, CPU saturation, DB
outage-vs-pool-exhaustion, recovery, runbook-only, empty source) and decides,
purely from code, whether the *evidence actually collected for this incident*
supports it.

This service performs NO confidence math -- it only produces
``ClaimValidationFinding`` records. ``hypothesis_service.calibrate_hypotheses``
and ``finalize_root_cause`` turn those findings into confidence penalties and
downgraded wording.
"""
from __future__ import annotations

import logging
import re

from app.domain.enums.provenance import EvidenceProvenance
from app.domain.models.claim_validation import ClaimCategory, ClaimValidationFinding
from app.domain.models.evidence import Evidence
from app.domain.models.hypothesis import Hypothesis
from app.domain.models.incident import Incident

logger = logging.getLogger(__name__)

_OOM_PATTERNS = (
    r"oom\s*killed",
    r"oomkilled",
    r"exit\s*cod?e?\s*137",
    r"out\s*of\s*memory",
    r"memory\s*limit\s*exceeded",
    r"killed\s*by\s*(k8s|kubernetes|the\s*kernel)",
)
_OOM = re.compile("|".join(_OOM_PATTERNS), re.IGNORECASE)

_CLBO_PATTERNS = (
    r"crash\s*loop(\s*back\s*-?\s*off)?",
    r"crashloopb?ackoff",
    r"back\s*-?\s*off\s*(restart)?",
    r"restart(ing)?\s*.*\bcrash",
)
_CLBO = re.compile("|".join(_CLBO_PATTERNS), re.IGNORECASE)

_CPU_PATTERNS = (
    r"cpu.{0,30}(saturat|spik|pinned|exhaust|at\s*100|~?\s*9\d\s*%)",
    r"high\s*cpu",
    r"cpu\s*usage",
    r"cpu\s*bound",
    r"processor\s*(usage|saturation)",
)
_CPU = re.compile("|".join(_CPU_PATTERNS), re.IGNORECASE)

_DB_DOWN_PATTERNS = (
    r"(database|postgres|mysql|sql\s*server|mongo(db)?|datastore|db\s*server)"
    + r".{0,60}\b(unreachable|outage|offline|not\s*reachable|cannot\s*connect"
    + r"|cannot\s*be\s*reached|couldn'?t\s*connect|is\s*down|went\s*down|down\b)",
    r"(database|db)\b.{0,40}\boutage",
)
_DB_DOWN = re.compile("|".join(_DB_DOWN_PATTERNS), re.IGNORECASE)

_POOL_MARKERS = re.compile(
    r"pool|hikari|saturat|exhaust|max_connections|SQLTransientConnectionException"
    r"|connection\s*refused|wait\s*queue|waiting",
    re.IGNORECASE,
)

_DB_DOWN_TELEMETRY = re.compile(
    r"(db|database|mysql|postgres).{0,40}\b(unreachable|outage|offline|is\s*down|went\s*down)",
    re.IGNORECASE,
)

_RECOVERY_PATTERNS = (
    r"\b(?:has\s+)?recovered\b",
    r"\brecovery\b",
    r"back\s*to\s*normal",
    r"stabilized",
    r"returned\s*to\s*baseline",
    r"resolved",
    r"deferred\s*charges?\s*(settled|drain)",
)
_RECOVERY = re.compile("|".join(_RECOVERY_PATTERNS), re.IGNORECASE)

_PENALTY_OOM = 0.15
_PENALTY_CLBO = 0.15
_PENALTY_CPU = 0.15
_PENALTY_DB = 0.15
_PENALTY_RECOVERY = 0.10
_PENALTY_EMPTY = 0.15


def _corpus_text(incident: Incident | None, evidence: list[Evidence], hypothesis: Hypothesis) -> str:
    """Text the claim checker may pivot on: cited evidence + incident telemetry."""
    parts: list[str] = []
    by_id = {e.evidence_id: e for e in evidence}
    for cid in hypothesis.supporting_evidence:
        ev = by_id.get(cid)
        if ev is None:
            if cid.startswith("runbook:"):
                parts.append(ev.finding if ev else cid)  # cited runbook chunk text
            continue
        parts.append(ev.finding)
        for value in (ev.raw_data or {}).values():
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, list) and all(isinstance(i, str) for i in value):
                parts.extend(value)
    if incident is not None:
        parts.extend(incident.raw_logs)
        parts.append(" ".join(str(e) for e in incident.raw_events))
        parts.append(
            " ".join(str(a.get("alert_name") or a.get("name") or a) for a in incident.raw_alerts)
        )
        parts.append(
            " ".join(f"{k}={v}" for k, v in (incident.raw_metrics or {}).items())
        )
    return "\n".join(p for p in parts if p)


def _cited_evidence(
    incident: Incident | None, evidence: list[Evidence], hypothesis: Hypothesis
) -> tuple[list[str], list[Evidence]]:
    """(evidence-ids / evidence objects) the hypothesis actually cites."""
    by_id = {e.evidence_id: e for e in evidence}
    cited = [by_id[cid] for cid in hypothesis.supporting_evidence if cid in by_id]
    names = list(hypothesis.supporting_evidence)
    return names, cited


def _evidence_empty(ev: Evidence) -> bool:
    """An evidence item that exists but had no telemetry behind it."""
    if ev.provenance != EvidenceProvenance.REPORTED:
        return False
    if ev.severity not in ("info",):
        return False
    rd = ev.raw_data or {}
    if rd.get("error"):
        return True
    if "telemetry_available" in rd:
        return not bool(rd.get("telemetry_available"))
    return rd.get("log_count") == 0 and not rd.get("retrieved_documents")


def _has_observed(evidence: list[Evidence], hypothesis: Hypothesis) -> bool:
    by_id = {e.evidence_id: e for e in evidence}
    return any(
        e.provenance == EvidenceProvenance.OBSERVED
        for cid in hypothesis.supporting_evidence
        if (e := by_id.get(cid)) is not None
    )


def _claim_finding(
    hypothesis: Hypothesis,
    category: ClaimCategory,
    claim: str,
    supported: bool,
    penalty: float,
    qualifier: str,
    detail: str,
) -> ClaimValidationFinding | None:
    if not claim:
        return None
    return ClaimValidationFinding(
        hypothesis_id=hypothesis.hypothesis_id,
        category=category,
        claim=claim[:120],
        supported=supported,
        penalty=penalty,
        qualifier=qualifier,
        detail=detail,
    )


def _validate_oomkilled(
    h: Hypothesis, corpus: str, cited: list[Evidence]
) -> ClaimValidationFinding | None:
    m = _OOM.search(h.description)
    if not m:
        return None
    supported = bool(
        re.search(r"\boom\b|exit code 137|exit code 137|out of memory", corpus, re.IGNORECASE)
    )
    return _claim_finding(
        h,
        ClaimCategory.OOMKILLED,
        m.group(0),
        supported,
        0.0 if supported else _PENALTY_OOM,
        "" if supported else
        "reported OOMKilled (no OOMKilled / exit-code-137 / restart signal in observed telemetry)",
        "detected OOMKilled claim" + ("; supported by observed memory signals" if supported else " but no telemetry" ),
    )


def _validate_crashloopbackoff(
    h: Hypothesis, corpus: str, cited: list[Evidence]
) -> ClaimValidationFinding | None:
    m = _CLBO.search(h.description)
    if not m:
        return None
    supported = bool(
        re.search(r"crash\s*loop|back\s*-?\s*off|restart", corpus, re.IGNORECASE)
    )
    return _claim_finding(
        h,
        ClaimCategory.CRASHLOOPBACKOFF,
        m.group(0),
        supported,
        0.0 if supported else _PENALTY_CLBO,
        "" if supported else
        "reported CrashLoopBackOff (no matching Kubernetes state/events)",
        "detected CrashLoopBackOff claim" + ("; supported by observed Kubernetes state/events" if supported else " but no matching K8s telemetry"),
    )


def _validate_cpu_saturation(
    h: Hypothesis, corpus: str, cited: list[Evidence], incident: Incident | None
) -> ClaimValidationFinding | None:
    m = _CPU.search(h.description)
    if not m:
        return None
    has_cpu_metric = any(
        "cpu" in str(key).lower()
        for key, _ in (incident.raw_metrics or {}).items()
    ) if incident is not None else False
    has_cpu_mention = bool(re.search(r"\bcpu\b", corpus, re.IGNORECASE))
    features = _metric_references(cited)
    supported = has_cpu_metric or has_cpu_mention or bool(features & {"cpu"})
    return _claim_finding(
        h,
        ClaimCategory.CPU_SATURATION,
        m.group(0),
        supported,
        0.0 if supported else _PENALTY_CPU,
        "" if supported else "reported CPU saturation (no CPU metrics available)",
        "detected CPU saturation claim" + ("; supported by CPU metrics" if supported else " but no CPU metric evidence"),
    )


def _validate_db_outage(
    h: Hypothesis, corpus: str, cited: list[Evidence]
) -> ClaimValidationFinding | None:
    m = _DB_DOWN.search(h.description)
    if not m:
        return None
    pool_only = bool(_POOL_MARKERS.search(corpus))
    if pool_only:
        # Evidence shows connection-pool/dependency exhaustion, not a DB outage.
        return _claim_finding(
            h,
            ClaimCategory.DB_OUTAGE,
            m.group(0),
            False,
            0.0,  # reword, not penalize: real telemetry still exists
            "reported as '<claim>' but observed evidence shows connection-pool/dependency exhaustion, not a DB outage",
            "DB outage claim downgraded to connection-pool exhaustion",
        )
    if _DB_DOWN_TELEMETRY.search(corpus):
        return _claim_finding(
            h,
            ClaimCategory.DB_OUTAGE,
            m.group(0),
            True,
            0.0,
            "",
            "DB outage claim supported by observed telemetry",
        )
    return _claim_finding(
        h,
        ClaimCategory.DB_OUTAGE,
        m.group(0),
        False,
        _PENALTY_DB,
        "reported as '<claim>' (no DB outage or connection-pool telemetry available)",
        "DB outage claim unsupported: neither DB-down nor pool-exhaustion telemetry present",
    )


def _validate_recovery(
    h: Hypothesis, corpus: str, cited: list[Evidence]
) -> ClaimValidationFinding | None:
    m = _RECOVERY.search(h.description)
    if not m:
        return None
    # CONTEXT (runbook) prose may legitimately describe recovery *guidance*;
    # it asserts nothing about this incident, so it is qualified, not penalized.
    penalty = _PENALTY_RECOVERY if h.provenance != EvidenceProvenance.CONTEXT else 0.0
    return _claim_finding(
        h,
        ClaimCategory.RECOVERY,
        m.group(0),
        False,
        penalty,
        "reported recovery (no post-remediation recovery evidence)",
        "recovery claim is never treated as verified without post-remediation recovery evidence",
    )


def _validate_runbook_only(h: Hypothesis) -> ClaimValidationFinding | None:
    if h.provenance != EvidenceProvenance.CONTEXT:
        return None
    return ClaimValidationFinding(
        hypothesis_id=h.hypothesis_id,
        category=ClaimCategory.RUNBOOK_ONLY,
        claim=h.description[:120],
        supported=False,
        penalty=0.0,
        qualifier="runbook guidance (CONTEXT): symptom not independently verified",
        detail="runbook-sourced hypothesis; useful for remediation relevance only",
    )


def _validate_empty_sources(
    h: Hypothesis, cited_names: list[str], cited: list[Evidence]
) -> list[ClaimValidationFinding]:
    findings: list[ClaimValidationFinding] = []
    for cid, ev in zip(cited_names, cited):
        if _evidence_empty(ev):
            findings.append(
                ClaimValidationFinding(
                    hypothesis_id=h.hypothesis_id,
                    category=ClaimCategory.EMPTY_SOURCE,
                    claim=cid,
                    supported=False,
                    penalty=_PENALTY_EMPTY,
                    qualifier=f"telemetry unavailable ('{cid}')",
                    detail=f"hypothesis cites '{cid}' but that evidence item had no available telemetry",
                )
            )
    return findings


def _metric_references(cited: list[Evidence]) -> set[str]:
    features: set[str] = set()
    for ev in cited:
        for value in (ev.raw_data or {}).values():
            if isinstance(value, str) and "cpu" in value.lower():
                features.add("cpu")
    return features


def validate_hypotheses(
    incident: Incident | None,
    evidence: list[Evidence] | None,
    hypotheses: list[Hypothesis] | None,
) -> list[ClaimValidationFinding]:
    """Run every deterministic claim check over ``hypotheses``.

    Pure validation: no mutation, no confidence math. Callers (the RCA node and
    the RCA service) feed the result to hypothesis_service for calibration.
    """
    if not hypotheses:
        return []
    evidence = evidence or []
    findings: list[ClaimValidationFinding] = []
    for h in hypotheses:
        corpus = _corpus_text(incident, evidence, h)
        cited_names, cited = _cited_evidence(incident, evidence, h)
        for finding in (
            _validate_oomkilled(h, corpus, cited),
            _validate_crashloopbackoff(h, corpus, cited),
            _validate_cpu_saturation(h, corpus, cited, incident),
            _validate_db_outage(h, corpus, cited),
            _validate_recovery(h, corpus, cited),
            _validate_runbook_only(h),
        ):
            if finding is not None:
                findings.append(finding)
        findings.extend(_validate_empty_sources(h, cited_names, cited))
    if findings:
        logger.info(
            "claim validation produced %d finding(s): %s",
            len(findings),
            [f"{f.hypothesis_id}:{f.category.value}" for f in findings],
        )
    return findings