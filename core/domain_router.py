"""Domain classification gate between the neural layer and the symbolic engine.

The symbolic engine (core.symbolic_engine) exposes a fixed set of rule
domains (tort, UCTA, RDC Concrete term classification, restraint of
trade, penalty). This module explicitly reports which of those domains
a payload actually engages, so the pipeline can flag an **unmapped
domain** instead of silently rendering an all-false/empty verdict for a
case outside current rule coverage.
"""
from __future__ import annotations

from typing import List

from core.schemas import LegalCaseFactPayload

KNOWN_DOMAINS = (
    "tort_negligence",  # Spandeck 2-stage duty of care test
    "contract_exemption_clause",  # UCTA 1977 s.2(1) / Schedule 2
    "contract_term_breach",  # RDC Concrete term classification
    "employment_restraint_of_trade",  # Man Financial two-tier test
    "liquidated_damages_penalty",  # Denka Advantech penalty rule
)


def classify_domains(payload: LegalCaseFactPayload) -> List[str]:
    """Return the known rule domains this payload actually engages."""
    domains: List[str] = []

    if payload.injury_type is not None or payload.factual_foreseeability:
        domains.append("tort_negligence")
    if payload.has_exemption_clause:
        domains.append("contract_exemption_clause")
    if payload.breach_term_type is not None:
        domains.append("contract_term_breach")
    if payload.has_restraint_of_trade_clause:
        domains.append("employment_restraint_of_trade")
    if payload.monthly_salary_sgd is not None and payload.liquidated_damages_sgd is not None:
        domains.append("liquidated_damages_penalty")

    return domains


def is_unmapped_domain(payload: LegalCaseFactPayload) -> bool:
    """True when the extracted payload doesn't engage any known rule domain."""
    return len(classify_domains(payload)) == 0
