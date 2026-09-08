"""Deterministic plain-English rendering of symbolic verdicts.

This module NEVER makes a legal judgment - it only formats results
already computed by the symbolic engine / procedural calculator into
human-readable prose for the chat UI.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.schemas import LegalCaseFactPayload


def render_legal_advice_summary(
    payload: LegalCaseFactPayload,
    deduction: Optional[Dict[str, Any]],
    limitation: Optional[Dict[str, Any]],
    graph_result: Dict[str, Any],
    penalty_check: Optional[Dict[str, Any]] = None,
    undervalue_check: Optional[Dict[str, Any]] = None,
    additional_graph_results: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Format already-computed verdicts into readable prose."""
    if deduction is None:
        return "No deterministic verdict could be derived - the request was denied at the SAFR gate."

    lines = []

    if graph_result.get("warning"):
        lines.append(f"⚠️ {graph_result['warning']}")
    for extra_result in additional_graph_results or []:
        if extra_result.get("warning"):
            lines.append(f"⚠️ {extra_result['warning']}")

    rdc = deduction["rdc_concrete"]
    if payload.breach_term_type is not None:
        term_label = payload.breach_term_type.value.replace("_", " ")
        lines.append(
            f"The breached term was classified as a **{term_label}** "
            "(*RDC Concrete v Sato Kogyo* [2007] 4 SLR(R) 413)."
        )
        if rdc["right_to_terminate"]:
            lines.append("Right to terminate the contract: **available**.")
        else:
            lines.append(
                "Right to terminate the contract: **not available** on these facts "
                "— only damages may be claimed."
            )
        if rdc["claim_damages"]:
            lines.append("A claim for damages arising from the breach: **is available**.")

    if payload.has_exemption_clause:
        ucta = deduction["ucta"]
        if ucta["clause_void_s2_1"]:
            lines.append(
                "The exemption clause is **automatically void** under UCTA s.2(1) "
                "(death/personal injury exclusions cannot be excluded)."
            )
        elif ucta["unreasonable_schedule_2"]:
            lines.append(
                "The exemption clause is **unreasonable and unenforceable** under "
                "UCTA Schedule 2 (unequal bargaining power, standard form terms, "
                "no inducement offered)."
            )
        else:
            lines.append("The exemption clause **passes** the UCTA reasonableness test.")

    restraint = deduction.get("restraint_of_trade") or {}
    if restraint.get("clause_present"):
        if restraint["void"]:
            lines.append(
                "The restraint of trade clause is **void and unenforceable** under the "
                "*Man Financial* two-tier test (*Man Financial (S) Pte Ltd v Wong Bark "
                "Chuan David* [2008] 1 SLR(R) 663) — no legitimate proprietary interest, "
                "or the duration/geographic scope is unreasonable."
            )
        else:
            lines.append(
                "The restraint of trade clause **passes** the *Man Financial* two-tier "
                "reasonableness test."
            )

    if penalty_check is not None:
        if penalty_check["is_extravagant_penalty"]:
            lines.append(
                "The liquidated damages clause is an **unenforceable penalty** under "
                "*Denka Advantech Pte Ltd v Tan Yuanyuan* [2020] 2 SLR 1155 — "
                f"S${penalty_check['liquidated_damages_sgd']:,.0f} is extravagant against a "
                f"reasonable estimate cap of S${penalty_check['reasonable_estimate_cap_sgd']:,.0f}."
            )
        else:
            lines.append(
                "The liquidated damages clause **is enforceable** as a genuine pre-estimate "
                "of loss under *Denka Advantech Pte Ltd v Tan Yuanyuan* [2020] 2 SLR 1155."
            )

    if undervalue_check is not None:
        if undervalue_check["is_voidable_transaction"]:
            lines.append(
                "The transfer **is voidable as a transaction at an undervalue** under IRDA "
                f"2018 ss 224-226 — consideration of S${undervalue_check['consideration_paid_sgd']:,.0f} "
                f"fell short of the S${undervalue_check['asset_market_value_sgd']:,.0f} market value by "
                f"S${undervalue_check['shortfall_sgd']:,.0f}, within the "
                f"{undervalue_check['lookback_years_applicable']}-year look-back window, with insolvency "
                "presumed for a connected-person transaction."
            )
        else:
            lines.append(
                "The transfer **does not meet the test** for a voidable transaction at an "
                "undervalue under IRDA 2018 ss 224-226 on these facts."
            )

    # Only relevant for tort-flavoured disputes (an injury type or asserted
    # foreseeability) - otherwise this is noise on a pure contract claim.
    spandeck = deduction["spandeck"]
    if payload.injury_type is not None or payload.factual_foreseeability:
        if spandeck["duty_of_care_exists"]:
            lines.append("A duty of care is established under the *Spandeck* 2-stage test.")
        else:
            lines.append("No duty of care is established under the *Spandeck* 2-stage test.")

    if limitation:
        if limitation["is_statute_barred"]:
            lines.append(
                "⏰ The claim is **statute-barred** — the Limitation Act 1959 s.6(1)(a) "
                f"window expired on {limitation['limitation_expiry_date']}."
            )
        else:
            lines.append(
                "The claim remains within the Limitation Act 1959 s.6(1)(a) window, "
                f"valid until {limitation['limitation_expiry_date']}."
            )

    return "\n\n".join(lines) if lines else "No deterministic verdict could be derived from the extracted facts."
