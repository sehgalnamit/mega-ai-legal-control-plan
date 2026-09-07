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
