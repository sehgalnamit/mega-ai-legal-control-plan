"""Detects human-in-the-loop follow-up instructions that modify a
previously extracted case's facts (e.g. "what if Client C had access to
trade secrets?"), instead of re-parsing a brand new case from scratch.

This is what makes multi-turn HITL conversations work: a follow-up
message alone rarely contains enough text for `core.neural_parser` to
re-extract a full case, so we detect a small, explicit set of fact
edits and apply them to a copy of the previous turn's payload.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

_TRADE_SECRET_GRANT_RE = re.compile(
    r"(access to|had|has|given|gain(?:ed)? access to).{0,40}(trade secret|proprietary|confidential|source code)",
    re.IGNORECASE,
)
_TRADE_SECRET_DENY_RE = re.compile(
    r"(no|without|didn't have|did not have) (access to )?(trade secret|proprietary|confidential)",
    re.IGNORECASE,
)
_BREACH_DATE_RE = re.compile(
    r"(?:change|set|update).{0,40}breach date.{0,10}(\d{4}-\d{2}-\d{2})", re.IGNORECASE
)
_CLAIM_VALUE_RE = re.compile(
    r"(?:change|set|update).{0,40}claim(?: value)?.{0,10}s\$\s?([\d,]+(?:\.\d+)?)", re.IGNORECASE
)
_INDUCEMENT_GRANT_RE = re.compile(r"(offered|given|provided) (an? )?inducement", re.IGNORECASE)


@dataclass
class FactPatch:
    field_updates: Dict[str, Any]
    description: str


def detect_fact_patch(message: str) -> Optional[FactPatch]:
    """Return a set of field updates if the message looks like a HITL
    request to modify previously extracted facts, else None.
    """
    updates: Dict[str, Any] = {}
    descriptions = []

    # Check denial before grant: "no access to confidential info" would
    # otherwise also match the grant pattern's "access to ... confidential".
    if _TRADE_SECRET_DENY_RE.search(message):
        updates["has_trade_secrets_or_confidential_info"] = False
        descriptions.append("has_trade_secrets_or_confidential_info -> False")
    elif _TRADE_SECRET_GRANT_RE.search(message):
        updates["has_trade_secrets_or_confidential_info"] = True
        descriptions.append("has_trade_secrets_or_confidential_info -> True")

    date_match = _BREACH_DATE_RE.search(message)
    if date_match:
        updates["contract_breach_date"] = date_match.group(1)
        descriptions.append(f"contract_breach_date -> {date_match.group(1)}")

    claim_match = _CLAIM_VALUE_RE.search(message)
    if claim_match:
        updates["claim_value_sgd"] = float(claim_match.group(1).replace(",", ""))
        descriptions.append(f"claim_value_sgd -> {claim_match.group(1)}")

    if _INDUCEMENT_GRANT_RE.search(message):
        updates["received_inducement"] = True
        descriptions.append("received_inducement -> True")

    if not updates:
        return None

    return FactPatch(field_updates=updates, description="; ".join(descriptions))
