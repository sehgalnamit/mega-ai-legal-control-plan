"""Procedural (non-symbolic, non-neural) calendar arithmetic.

Limitation Act 1959 (Singapore), s.6(1)(a): actions founded on contract
must be brought within 6 years from the date the cause of action
accrued (here, the contract breach date). This is exact calendar math,
deliberately kept out of both the Datalog engine and the LLM.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Optional

LIMITATION_PERIOD_YEARS = 6


def check_limitation_period(breach_date_str: str, as_of: Optional[date] = None) -> Dict[str, object]:
    """Calculate the Limitation Act 1959 s.6(1)(a) expiry date for a
    contract breach and determine whether a claim is statute-barred.

    Args:
        breach_date_str: contract breach date in YYYY-MM-DD format.
        as_of: reference "today" date; defaults to the current date.

    Returns:
        A dict with the breach date, expiry date, days remaining/overdue
        and an `is_statute_barred` flag.
    """
    breach_date = datetime.strptime(breach_date_str, "%Y-%m-%d").date()
    today = as_of or date.today()

    try:
        expiry_date = breach_date.replace(year=breach_date.year + LIMITATION_PERIOD_YEARS)
    except ValueError:
        # Handles 29 Feb breach dates rolling into a non-leap expiry year.
        expiry_date = breach_date.replace(
            month=2, day=28, year=breach_date.year + LIMITATION_PERIOD_YEARS
        )

    is_statute_barred = today > expiry_date
    days_delta = (expiry_date - today).days

    return {
        "breach_date": breach_date.isoformat(),
        "limitation_expiry_date": expiry_date.isoformat(),
        "reference_date": today.isoformat(),
        "is_statute_barred": is_statute_barred,
        "days_remaining": max(days_delta, 0),
        "days_overdue": abs(days_delta) if is_statute_barred else 0,
        "statutory_basis": (
            "Limitation Act 1959 (Singapore) s.6(1)(a) - 6 years from accrual "
            "of the cause of action."
        ),
    }


# Denka Advantech Pte Ltd v Tan Yuanyuan [2020] 2 SLR 1155 (simplified):
# a liquidated sum is a bright-line numeric comparison against a proxy
# for the greatest conceivable loss, not an open-textured multi-factor
# test - kept here as exact arithmetic rather than a pyDatalog rule, the
# same way limitation-period math is kept out of the symbolic engine.
PENALTY_REASONABLE_ESTIMATE_MONTHS_MULTIPLIER = 12


def check_liquidated_damages_penalty(
    monthly_salary_sgd: float,
    liquidated_damages_sgd: float,
    months_multiplier: int = PENALTY_REASONABLE_ESTIMATE_MONTHS_MULTIPLIER,
) -> Dict[str, object]:
    """Flag a liquidated damages clause as an unenforceable penalty if it
    is extravagant and unconscionable relative to a reasonable estimate
    of the greatest conceivable loss (approximated as `months_multiplier`
    months of salary).
    """
    reasonable_estimate_cap = monthly_salary_sgd * months_multiplier
    is_extravagant_penalty = liquidated_damages_sgd > reasonable_estimate_cap

    return {
        "monthly_salary_sgd": monthly_salary_sgd,
        "liquidated_damages_sgd": liquidated_damages_sgd,
        "reasonable_estimate_cap_sgd": reasonable_estimate_cap,
        "is_extravagant_penalty": is_extravagant_penalty,
        "clause_enforceable": not is_extravagant_penalty,
        "statutory_basis": (
            "Denka Advantech Pte Ltd v Tan Yuanyuan [2020] 2 SLR 1155 - penalty "
            "rule (extravagant/unconscionable sums are unenforceable)."
        ),
    }


# Insolvency, Restructuring and Dissolution Act 2018 (IRDA) ss 224-226
# (simplified): a transaction at an undervalue is voidable if it falls
# within the statutory look-back window measured from the winding-up
# date, and insolvency is statutorily presumed for connected-person
# (e.g. group/associate) transactions under s 226. Kept as exact
# date/numeric arithmetic rather than a pyDatalog rule, consistent with
# the Limitation Act and Denka Advantech penalty calculators above.
UNDERVALUE_LOOKBACK_YEARS = {True: 3, False: 2}  # connected person vs. unconnected


def check_undervalue_transaction(
    asset_market_value_sgd: float,
    consideration_paid_sgd: float,
    is_connected_person: bool,
    transaction_date_str: str,
    winding_up_date_str: str,
) -> Dict[str, object]:
    """Evaluate an IRDA s 224 transaction-at-undervalue clawback claim."""
    transaction_date = datetime.strptime(transaction_date_str, "%Y-%m-%d").date()
    winding_up_date = datetime.strptime(winding_up_date_str, "%Y-%m-%d").date()

    lookback_years = UNDERVALUE_LOOKBACK_YEARS[is_connected_person]
    try:
        lookback_cutoff = winding_up_date.replace(year=winding_up_date.year - lookback_years)
    except ValueError:
        lookback_cutoff = winding_up_date.replace(month=2, day=28, year=winding_up_date.year - lookback_years)

    within_lookback_window = transaction_date >= lookback_cutoff
    shortfall_sgd = max(asset_market_value_sgd - consideration_paid_sgd, 0.0)
    is_undervalue = shortfall_sgd > 0
    # s 226: insolvency at the time of the transaction is statutorily
    # presumed for connected-person transactions; otherwise it must be
    # proven separately (outside this calculator's scope).
    insolvency_presumed = is_connected_person

    is_voidable_transaction = is_undervalue and within_lookback_window and insolvency_presumed

    return {
        "asset_market_value_sgd": asset_market_value_sgd,
        "consideration_paid_sgd": consideration_paid_sgd,
        "shortfall_sgd": shortfall_sgd,
        "is_undervalue": is_undervalue,
        "lookback_years_applicable": lookback_years,
        "lookback_cutoff_date": lookback_cutoff.isoformat(),
        "within_lookback_window": within_lookback_window,
        "insolvency_presumed": insolvency_presumed,
        "is_voidable_transaction": is_voidable_transaction,
        "statutory_basis": (
            "Insolvency, Restructuring and Dissolution Act 2018 (IRDA) ss 224-226 - "
            "transaction at an undervalue with connected-person insolvency presumption."
        ),
    }


# Protection from Harassment Act 2014 (POHA) ss 3, 4 & 15 (simplified): a
# course of conduct (publishing identifying information and/or inciting
# third parties to harass) that causes alarm, distress, or fear grounds
# a Protection Order. Kept as a plain boolean test rather than a
# pyDatalog rule for simplicity - there is no negation/derived-predicate
# composition needed here, unlike the Man Financial two-tier test.
def evaluate_poha_harassment_claim(
    publishes_identifying_information: bool,
    urges_third_party_harassment: bool,
    causes_alarm_distress_or_fear: bool,
) -> Dict[str, object]:
    """Evaluate a POHA harassment claim for a civil Protection Order."""
    course_of_conduct_established = publishes_identifying_information or urges_third_party_harassment
    doxxing_with_incitement = publishes_identifying_information and urges_third_party_harassment
    protection_order_likely = course_of_conduct_established and causes_alarm_distress_or_fear

    return {
        "course_of_conduct_established": course_of_conduct_established,
        "doxxing_with_incitement_to_third_party_harassment": doxxing_with_incitement,
        "causes_alarm_distress_or_fear": causes_alarm_distress_or_fear,
        "protection_order_likely": protection_order_likely,
        "statutory_basis": (
            "Protection from Harassment Act 2014 (POHA) ss 3, 4 & 15 - a course of conduct causing "
            "alarm, distress, or fear grounds a civil Protection Order; publishing identifying "
            "information combined with inciting third-party harassment strengthens the case for "
            "urgent interim relief."
        ),
    }
