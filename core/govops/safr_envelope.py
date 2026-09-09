"""MAS SAFR (Safeguards for Agentic Finance at Runtime) governance envelope.

Evaluates the risk of an LLM-extracted fact payload *before* it is
handed to the deterministic symbolic engine, and assigns a runtime
disposition. This module never decides the legal verdict itself - it
only decides whether the pipeline may proceed automatically, must be
observed, escalated for human sign-off, or denied outright.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from core.schemas import LegalCaseFactPayload

HIGH_VALUE_CLAIM_THRESHOLD = 10_000.0
# Deliberately above the offline mock parser's fixed 0.65 confidence, so
# any mock-parsed (i.e. non-LLM-verified) extraction on a real dispute
# is escalated for human review rather than silently auto-executed.
MIN_EXTRACTION_CONFIDENCE = 0.7


class SafrDisposition(str, Enum):
    AUTO_EXECUTE = "AUTO_EXECUTE"
    OBSERVE = "OBSERVE"
    ESCALATE = "ESCALATE"
    DENY = "DENY"


@dataclass
class SafrEnvelopeResult:
    disposition: SafrDisposition
    verdict: str  # W3C baggage tri-state: ALLOW | DENY | ESCALATE
    risk_flags: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


def evaluate_safr_envelope(
    payload: LegalCaseFactPayload,
    extraction_confidence: float = 1.0,
    claim_value_usd: float = 0.0,
    extraction_contradictions: Optional[List[str]] = None,
    is_unmapped_domain: bool = False,
    matched_domains: Optional[List[str]] = None,
) -> SafrEnvelopeResult:
    """Risk-gate the neural-extracted payload before symbolic deduction."""
    risk_flags: List[str] = []
    reasons: List[str] = []
    matched_domains = matched_domains or []

    if is_unmapped_domain:
        risk_flags.append("UNMAPPED_DOMAIN")
        reasons.append(
            "No deterministic rule module covers this case's legal domain(s) - "
            "escalating instead of returning a silent all-false verdict."
        )

    if extraction_confidence < MIN_EXTRACTION_CONFIDENCE:
        risk_flags.append("LOW_EXTRACTION_CONFIDENCE")
        reasons.append(
            f"Neural extraction confidence {extraction_confidence:.2f} is below "
            f"threshold {MIN_EXTRACTION_CONFIDENCE:.2f}."
        )

    if extraction_contradictions:
        risk_flags.append("EXTRACTION_CONTRADICTION")
        reasons.extend(extraction_contradictions)

    if claim_value_usd >= HIGH_VALUE_CLAIM_THRESHOLD:
        risk_flags.append("HIGH_VALUE_CLAIM")
        reasons.append(
            f"Claim value {claim_value_usd:,.2f} meets/exceeds the "
            f"{HIGH_VALUE_CLAIM_THRESHOLD:,.2f} HITL escalation threshold."
        )

    if payload.injury_type is not None and payload.injury_type.value == "personal_injury_or_death":
        risk_flags.append("PERSONAL_INJURY_OR_DEATH")
        reasons.append("Payload involves death/personal injury - statutory bar territory (UCTA s.2(1)).")

    # Limitation Act 1959 s.6(1)(a) only bites on a historical breach of
    # contract claim (RDC Concrete term-breach domain) - an advisory matter
    # like a restraint-of-trade enforceability opinion has no accrued cause
    # of action, so a missing breach date there is not a risk signal.
    if payload.contract_breach_date is None and "employment_restraint_of_trade" not in matched_domains:
        if not matched_domains or "contract_term_breach" in matched_domains:
            risk_flags.append("MISSING_BREACH_DATE")
            reasons.append("No contract breach date extracted; limitation period cannot be computed.")

    if (
        "PERSONAL_INJURY_OR_DEATH" in risk_flags
        or "LOW_EXTRACTION_CONFIDENCE" in risk_flags
        or "EXTRACTION_CONTRADICTION" in risk_flags
        or "UNMAPPED_DOMAIN" in risk_flags
    ):
        disposition = SafrDisposition.ESCALATE
        verdict = "ESCALATE"
    elif risk_flags:
        disposition = SafrDisposition.OBSERVE
        verdict = "ALLOW"
    else:
        disposition = SafrDisposition.AUTO_EXECUTE
        verdict = "ALLOW"

    if not reasons:
        reasons.append("No risk factors detected; payload cleared for automatic symbolic deduction.")

    return SafrEnvelopeResult(disposition=disposition, verdict=verdict, risk_flags=risk_flags, reasons=reasons)
