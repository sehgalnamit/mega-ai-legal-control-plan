"""Tests for the IRDA 2018 ss 224-226 transaction-at-undervalue clawback
rule: procedural calculator, domain classification, and the full
Logistics Corp / Holding Co H insolvency test case end-to-end.
"""
from datetime import date

from core.domain_router import classify_domains, is_unmapped_domain
from core.neural_parser import parse_legal_case_text
from core.procedural_calculators import check_undervalue_transaction
from core.response_renderer import render_legal_advice_summary
from core.symbolic_engine import run_symbolic_deduction

LOGISTICS_CORP_CASE_TEXT = (
    "Client G is the court-appointed Liquidator of Logistics Corp Pte Ltd (wound up on 2026-02-01). "
    "During asset recovery audits, Client G discovered that on 2025-06-15 (7 months prior to liquidation), "
    "when Logistics Corp was already unable to pay its debts as they fell due, the company transferred "
    "title of a commercial warehouse worth S$2.8 Million to Holding Co H (its 100% parent) for S$100,000. "
    "Holding Co H claims the transfer was a legitimate corporate restructuring internal to the group and "
    "refuses to surrender the title. Client G wants to apply under IRDA to claw back the warehouse into "
    "the liquidation pool."
)


def test_undervalue_and_within_lookback_and_connected_person_is_voidable():
    result = check_undervalue_transaction(
        asset_market_value_sgd=2_800_000.0,
        consideration_paid_sgd=100_000.0,
        is_connected_person=True,
        transaction_date_str="2025-06-15",
        winding_up_date_str="2026-02-01",
    )

    assert result["is_undervalue"] is True
    assert result["within_lookback_window"] is True
    assert result["insolvency_presumed"] is True
    assert result["is_voidable_transaction"] is True
    assert result["shortfall_sgd"] == 2_700_000.0


def test_unconnected_person_transaction_outside_2_year_window_not_presumed_insolvent():
    result = check_undervalue_transaction(
        asset_market_value_sgd=1_000_000.0,
        consideration_paid_sgd=100.0,
        is_connected_person=False,
        transaction_date_str="2020-01-01",
        winding_up_date_str="2026-01-01",
    )

    assert result["is_undervalue"] is True
    assert result["within_lookback_window"] is False
    assert result["insolvency_presumed"] is False
    assert result["is_voidable_transaction"] is False


def test_fair_value_transaction_is_not_undervalue():
    result = check_undervalue_transaction(
        asset_market_value_sgd=500_000.0,
        consideration_paid_sgd=500_000.0,
        is_connected_person=True,
        transaction_date_str="2025-06-15",
        winding_up_date_str="2026-02-01",
    )

    assert result["is_undervalue"] is False
    assert result["is_voidable_transaction"] is False


def test_logistics_corp_case_is_now_a_mapped_domain_not_escalated_as_unmapped():
    """Regression test: this exact fact pattern previously fell through as
    UNMAPPED_DOMAIN even though it is a textbook IRDA undervalue claim.
    """
    payload = parse_legal_case_text(LOGISTICS_CORP_CASE_TEXT, case_id="logistics-corp-1")

    assert payload.claim_value_sgd == 2_800_000.0
    assert payload.asset_market_value_sgd == 2_800_000.0
    assert payload.consideration_paid_sgd == 100_000.0
    assert payload.is_connected_person is True
    assert payload.transaction_date == "2025-06-15"
    assert payload.winding_up_date == "2026-02-01"

    domains = classify_domains(payload)
    assert "insolvency_undervalue_transaction" in domains
    assert is_unmapped_domain(payload) is False


def test_logistics_corp_case_produces_a_real_voidable_transaction_verdict():
    payload = parse_legal_case_text(LOGISTICS_CORP_CASE_TEXT, case_id="logistics-corp-2")
    check = check_undervalue_transaction(
        payload.asset_market_value_sgd,
        payload.consideration_paid_sgd,
        payload.is_connected_person,
        payload.transaction_date,
        payload.winding_up_date,
    )
    assert check["is_voidable_transaction"] is True

    deduction = run_symbolic_deduction(payload)
    summary = render_legal_advice_summary(
        payload, deduction, None, {"warning": None}, undervalue_check=check
    )
    assert "voidable as a transaction at an undervalue" in summary
    assert "Spandeck" not in summary
