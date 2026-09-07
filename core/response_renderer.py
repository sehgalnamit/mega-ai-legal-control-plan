"""Deterministic plain-English rendering of symbolic verdicts.

This module NEVER makes a legal judgment - it only formats results
already computed by the symbolic engine / procedural calculator into
human-readable prose for the chat UI.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.schemas import LegalCaseFactPayload


def render_legal_advice_summary(
    payload: LegalCaseFactPayload,
    deduction: Optional[Dict[str, Any]],
    limitation: Optional[Dict[str, Any]],
    graph_result: Dict[str, Any],
) -> str:
    """Format already-computed verdicts into readable prose."""
    if deduction is None:
        return "No deterministic verdict could be derived - the request was denied at the SAFR gate."

    lines = []

    if graph_result.get("warning"):
        lines.append(f"⚠️ {graph_result['warning']}")

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

    spandeck = deduction["spandeck"]
    if payload.factual_foreseeability or payload.proximity_type.value != "no_proximity":
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
