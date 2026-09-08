"""Post-extraction sanity checks that catch neural-parser contradictions
before they reach the symbolic engine.

This is the "validator gate" between the neural and symbolic layers:
it never decides a legal outcome, it only flags cases where a
structured field appears to contradict the literal contract language,
so the GovOps SAFR envelope can escalate for human review instead of
silently trusting a possibly-mistaken classification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from core.schemas import LegalCaseFactPayload

_NOT_A_CONDITION_PHRASES = ("independent undertaking", "not a condition", "not a term")
_EXEMPTION_CLAUSE_PHRASES = ("exemption clause", "exclusion clause", "excluding all", "limitation of liability")


@dataclass
class ConsistencyCheckResult:
    is_consistent: bool
    contradictions: List[str] = field(default_factory=list)


def validate_extraction_consistency(payload: LegalCaseFactPayload, raw_text: str) -> ConsistencyCheckResult:
    """Flag cases where a structured field contradicts the raw contract text."""
    contradictions: List[str] = []
    lowered = raw_text.lower()

    if payload.breach_term_type is not None and payload.breach_term_type.value == "condition":
        if any(phrase in lowered for phrase in _NOT_A_CONDITION_PHRASES):
            contradictions.append(
                "Extracted breach_term_type='condition' contradicts express contract "
                "language describing the term as an independent undertaking / not a condition."
            )

    if payload.has_exemption_clause is False and any(phrase in lowered for phrase in _EXEMPTION_CLAUSE_PHRASES):
        contradictions.append(
            "has_exemption_clause=False but the raw text explicitly references an exemption/exclusion clause."
        )

    if payload.standard_form_contract is False and "standard form" in lowered:
        contradictions.append(
            "standard_form_contract=False but the raw text explicitly describes a standard form contract."
        )

    return ConsistencyCheckResult(is_consistent=not contradictions, contradictions=contradictions)
