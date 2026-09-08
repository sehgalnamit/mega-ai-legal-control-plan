"""Regression tests for the currency-amount parser ("S$2.8 Million" must
not be silently parsed as 2.8).
"""
from core.neural_parser import parse_legal_case_text

INSOLVENCY_CASE_TEXT = (
    "Client G is the court-appointed Liquidator of Logistics Corp Pte Ltd (wound up on 2026-02-01). "
    "Client G discovered that the company transferred title of a commercial warehouse worth S$2.8 Million "
    "to Holding Co H (its 100% parent) for S$100,000. Client G wants to apply under IRDA to claw back the "
    "warehouse into the liquidation pool."
)


def test_million_suffix_is_parsed_as_a_multiplier_not_a_decimal():
    payload = parse_legal_case_text(INSOLVENCY_CASE_TEXT, case_id="currency-test")

    assert payload.claim_value_sgd == 2_800_000.0


def test_bare_amount_without_suffix_still_parses_correctly():
    text = "The tenant caused S$45,000 in damage to the leased premises."
    payload = parse_legal_case_text(text, case_id="currency-test-2")

    assert payload.claim_value_sgd == 45_000.0


def test_thousand_suffix_is_parsed_as_a_multiplier():
    text = "The claim value is S$20 thousand for the defective goods."
    payload = parse_legal_case_text(text, case_id="currency-test-3")

    assert payload.claim_value_sgd == 20_000.0
