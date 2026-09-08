"""Domain classification gate between the neural layer and the symbolic engine.

The symbolic engine (core.symbolic_engine) exposes a fixed set of rule
domains (tort, UCTA, RDC Concrete term classification, restraint of
trade, penalty). This module explicitly reports which of those domains
a payload actually engages, so the pipeline can flag an **unmapped
domain** instead of silently rendering an all-false/empty verdict for a
case outside current rule coverage.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.schemas import LegalCaseFactPayload

KNOWN_DOMAINS = (
    "tort_negligence",  # Spandeck 2-stage duty of care test
    "contract_exemption_clause",  # UCTA 1977 s.2(1) / Schedule 2
    "contract_term_breach",  # RDC Concrete term classification
    "employment_restraint_of_trade",  # Man Financial two-tier test
    "liquidated_damages_penalty",  # Denka Advantech penalty rule
    "insolvency_undervalue_transaction",  # IRDA 2018 ss 224-226
    "poha_harassment",  # POHA 2014 ss 3, 4, 15
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
    if (
        payload.has_insolvency_clawback_claim
        and payload.asset_market_value_sgd is not None
        and payload.consideration_paid_sgd is not None
        and payload.transaction_date is not None
        and payload.winding_up_date is not None
    ):
        domains.append("insolvency_undervalue_transaction")
    if payload.has_harassment_claim:
        domains.append("poha_harassment")

    return domains


def build_skipped_deduction_notice(domain_labels: Optional[List[str]] = None) -> Dict[str, Any]:
    """Synthetic "deduction skipped" payload for unmapped-domain cases.

    Ensures the proof-trace panel never shows a misleading Spandeck/UCTA/
    RDC Concrete/restraint-of-trade deduction (e.g. `duty_of_care_exists
    => False`) for a case that engages none of those legal tests.
    """
    labels = domain_labels or ["Unclassified"]
    return {
        "engine_status": "DYNAMIC_SYNTHESIS_REQUIRED",
        "proof_trace": [
            f"INFO: Domain(s) {labels} have no loaded deterministic rule "
            "module - Spandeck/UCTA/RDC Concrete/restraint-of-trade deduction skipped."
        ],
    }


def is_unmapped_domain(payload: LegalCaseFactPayload) -> bool:
    """True when the extracted payload doesn't engage any known rule domain."""
    return len(classify_domains(payload)) == 0
