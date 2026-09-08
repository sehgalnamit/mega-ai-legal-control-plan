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
    poha_check: Optional[Dict[str, Any]] = None,
    additional_graph_results: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Format already-computed verdicts into the same 4-section practitioner
    memo format used by the LLM provisional-analysis fallback, so a lawyer
    sees a consistent structure whether the case was handled by the
    deterministic symbolic engine or escalated for a provisional LLM draft.
    """
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

    if poha_check is not None:
        if poha_check["protection_order_likely"]:
            lines.append(
                "A civil **Protection Order is likely** to be granted under the Protection from "
                "Harassment Act 2014 (POHA) ss 3, 4 & 15"
                + (
                    ", with a strong case for urgent interim relief given the combination of "
                    "doxxing and incitement to third-party harassment."
                    if poha_check["doxxing_with_incitement_to_third_party_harassment"]
                    else "."
                )
            )
        else:
            lines.append(
                "The facts **do not establish** the course-of-conduct-plus-alarm/distress test "
                "for a Protection Order under POHA ss 3, 4 & 15 on these facts alone."
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

    procedural_lines = _procedural_next_steps(payload, deduction, undervalue_check, poha_check)
    next_steps_body = "\n".join(procedural_lines) if procedural_lines else (
        "- Escalate to the supervising attorney to determine the appropriate next steps; no "
        "deterministic procedural mapping applies to these facts."
    )
    if procedural_lines:
        next_steps_body += (
            "\n\n_Confirm the exact filing track, forms, and deadlines against the current Rules "
            "of Court 2021, applicable Practice Directions, and the e-Litigation system before filing._"
        )

    overview_lines = _case_overview_lines(payload)
    checklist_lines = _document_checklist(payload, deduction, undervalue_check, poha_check)

    sections = [
        "## 1. Case Overview & Key Facts",
        "\n".join(overview_lines),
        "## 2. Preliminary Legal Assessment & Risk Mapping",
        "\n\n".join(lines) if lines else "No deterministic verdict could be derived from the extracted facts.",
        "## 3. Practitioner Intake & Document Checklist",
        "\n".join(checklist_lines),
        "## 4. Immediate Tactical Next Steps",
        next_steps_body,
    ]
    return "\n\n".join(sections)


def _case_overview_lines(payload: LegalCaseFactPayload) -> List[str]:
    """Restate already-extracted structured facts as a readable overview -
    never inventing a new fact, only formatting what the neural layer or
    fact-patch follow-up already put on the payload.
    """
    lines = [f"- Case reference: `{payload.case_id}`."]
    if payload.cited_precedent and payload.cited_precedent != "Unspecified Precedent":
        lines.append(f"- Cited precedent: *{payload.cited_precedent}*.")
    if payload.contract_breach_date:
        lines.append(f"- Contract breach date: {payload.contract_breach_date}.")
    if payload.claim_value_sgd:
        lines.append(f"- Claim value: S${payload.claim_value_sgd:,.0f}.")
    if payload.transaction_date and payload.winding_up_date:
        lines.append(
            f"- Impugned transaction date: {payload.transaction_date}; winding-up date: "
            f"{payload.winding_up_date}."
        )
    if payload.asset_market_value_sgd is not None and payload.consideration_paid_sgd is not None:
        lines.append(
            f"- Asset market value: S${payload.asset_market_value_sgd:,.0f}; consideration paid: "
            f"S${payload.consideration_paid_sgd:,.0f}."
        )
    if payload.restraint_duration_months is not None:
        scope_suffix = f"; geographic scope: {payload.restraint_geography_scope}." if payload.restraint_geography_scope else "."
        lines.append(f"- Restraint of trade duration: {payload.restraint_duration_months} months{scope_suffix}")
    if payload.monthly_salary_sgd is not None and payload.liquidated_damages_sgd is not None:
        lines.append(
            f"- Monthly salary: S${payload.monthly_salary_sgd:,.0f}; liquidated damages clause: "
            f"S${payload.liquidated_damages_sgd:,.0f}."
        )
    if payload.has_harassment_claim:
        lines.append(
            "- Harassment claim pleaded: publishes identifying information="
            f"{payload.publishes_identifying_information}, urges third-party harassment="
            f"{payload.urges_third_party_harassment}, causes alarm/distress/fear="
            f"{payload.causes_alarm_distress_or_fear}."
        )
    return lines


def _document_checklist(
    payload: LegalCaseFactPayload,
    deduction: Dict[str, Any],
    undervalue_check: Optional[Dict[str, Any]],
    poha_check: Optional[Dict[str, Any]],
) -> List[str]:
    """Deterministic, rule-based intake checklist keyed off which rule
    modules actually fired for this payload - not an LLM guess."""
    items: List[str] = []
    if payload.breach_term_type is not None:
        items.append("- The executed contract (all clauses, not only the breached term) and any variations.")
        items.append("- Correspondence evidencing the breach date and any notice of termination given.")
    if payload.has_exemption_clause:
        items.append("- Evidence of the bargaining process (standard form terms? any inducement offered?).")
    restraint = (deduction or {}).get("restraint_of_trade") or {}
    if restraint.get("clause_present"):
        items.append(
            "- Evidence of any trade secrets/confidential information/client lists the employee "
            "actually had access to."
        )
    if undervalue_check is not None:
        items.append(
            "- Valuation evidence for the transferred asset and proof of the company's inability "
            "to pay its debts at the transaction date."
        )
    if poha_check is not None:
        items.append("- Screenshots/recordings of the offending posts, call logs, and evidence of distress caused.")
    if payload.injury_type is not None or payload.factual_foreseeability:
        items.append("- Evidence going to foreseeability and proximity for the Spandeck duty-of-care analysis.")
    if not items:
        items.append("- Confirm all facts above with the client and request supporting documentary evidence.")
    return items


def _procedural_next_steps(
    payload: LegalCaseFactPayload,
    deduction: Dict[str, Any],
    undervalue_check: Optional[Dict[str, Any]],
    poha_check: Optional[Dict[str, Any]],
) -> List[str]:
    """Deterministic, rule-based mapping from already-computed verdict flags
    to a likely Rules of Court 2021 filing track - never a new legal
    judgment, only a formatting layer over facts already decided above.
    """
    steps: List[str] = []
    rdc = deduction.get("rdc_concrete") or {}
    if payload.breach_term_type is not None and rdc.get("right_to_terminate"):
        steps.append(
            "- Consider an **Originating Claim** pleading breach of contract and claiming damages, "
            "particularized in a Statement of Claim; if urgent interim relief (e.g. an injunction) is "
            "needed, this is typically sought by Summons within the action, supported by an affidavit."
        )
    if undervalue_check is not None and undervalue_check.get("is_voidable_transaction"):
        steps.append(
            "- The liquidator may apply by **Originating Application** under IRDA s 224 for an order "
            "avoiding the transaction, supported by an affidavit exhibiting the transaction documents "
            "and evidence of insolvency."
        )
    if poha_check is not None and poha_check.get("protection_order_likely"):
        steps.append(
            "- An **Expedited Protection Order** may be sought by Originating Application under POHA "
            "s 13, supported by an affidavit; consider whether a Certificate of Urgency is warranted "
            "given the ongoing risk to personal safety."
        )
    restraint = deduction.get("restraint_of_trade") or {}
    if restraint.get("clause_present"):
        steps.append(
            "- If the counterparty applies for (or threatens) an interim injunction to enforce the "
            "restraint clause, prepare affidavit evidence addressing the *Man Financial* two-tier "
            "test, filed by Summons in response to that application."
        )
    return steps
