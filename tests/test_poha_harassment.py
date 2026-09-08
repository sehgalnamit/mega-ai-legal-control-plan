"""Tests for the POHA 2014 ss 3, 4 & 15 harassment/Protection Order rule,
and the full Telegram doxxing test case end-to-end.
"""
from core.domain_router import classify_domains, is_unmapped_domain
from core.neural_parser import parse_legal_case_text
from core.procedural_calculators import evaluate_poha_harassment_claim
from core.response_renderer import render_legal_advice_summary
from core.symbolic_engine import run_symbolic_deduction

DOXXING_CASE_TEXT = (
    "Client J is a senior HR director in Singapore. On 2026-07-10, an anonymous user launched a public "
    "Telegram channel exposing Client J's personal mobile phone number, residential address, and family "
    "photos. The posts explicitly urged subscribers to 'harass this corporate killer at her home address "
    "until she resigns.' Client J has since received over 80 abusive phone calls and threatening text "
    "messages at night, causing severe emotional distress and fear for personal safety. Client J wants an "
    "urgent court order under the Protection from Harassment Act (POHA) to compel Telegram to remove the "
    "channel and restrain the harasser."
)


def test_doxxing_plus_incitement_plus_distress_grants_protection_order():
    result = evaluate_poha_harassment_claim(
        publishes_identifying_information=True,
        urges_third_party_harassment=True,
        causes_alarm_distress_or_fear=True,
    )

    assert result["course_of_conduct_established"] is True
    assert result["doxxing_with_incitement_to_third_party_harassment"] is True
    assert result["protection_order_likely"] is True


def test_no_alarm_distress_or_fear_defeats_protection_order():
    result = evaluate_poha_harassment_claim(
        publishes_identifying_information=True,
        urges_third_party_harassment=False,
        causes_alarm_distress_or_fear=False,
    )

    assert result["protection_order_likely"] is False


def test_doxxing_case_is_now_mapped_not_escalated_as_unmapped():
    """Regression test: this exact fact pattern previously fell through as
    unmapped, with real_estate_property falsely matched via the
    'distress' keyword collision (emotional distress vs. landlord distress).
    """
    payload = parse_legal_case_text(DOXXING_CASE_TEXT, case_id="doxxing-1")

    assert payload.has_harassment_claim is True
    assert payload.publishes_identifying_information is True
    assert payload.urges_third_party_harassment is True
    assert payload.causes_alarm_distress_or_fear is True

    domains = classify_domains(payload)
    assert "poha_harassment" in domains
    assert is_unmapped_domain(payload) is False


def test_doxxing_case_produces_a_real_protection_order_verdict():
    payload = parse_legal_case_text(DOXXING_CASE_TEXT, case_id="doxxing-2")
    check = evaluate_poha_harassment_claim(
        payload.publishes_identifying_information,
        payload.urges_third_party_harassment,
        payload.causes_alarm_distress_or_fear,
    )
    assert check["protection_order_likely"] is True

    deduction = run_symbolic_deduction(payload)
    summary = render_legal_advice_summary(payload, deduction, None, {"warning": None}, poha_check=check)

    assert "Protection Order is likely" in summary
    assert "Spandeck" not in summary
