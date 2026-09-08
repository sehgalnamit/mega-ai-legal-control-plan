"""Tests for the Man Financial restraint-of-trade rule and the Denka
Advantech penalty-clause calculator, plus the multi-citation precedent
extraction fallback used by the TechCorp SG employment dispute scenario.
"""
from core.graph_gate import check_precedent_status
from core.neural_parser import parse_legal_case_text
from core.procedural_calculators import check_liquidated_damages_penalty
from core.response_renderer import render_legal_advice_summary
from core.schemas import LegalCaseFactPayload, ProximityType
from core.symbolic_engine import run_symbolic_deduction

TECHCORP_RESTRAINT_TEXT = (
    "Client C was employed as a Junior Software Developer by TechCorp SG (a "
    "Singapore-based software company) under a standard employment contract signed "
    "in 2024. Client C's monthly salary was S$4,500. Clause 22 (Restraint of Trade) "
    "stipulates: 'Upon termination of employment for any reason, the Employee shall "
    "not work for, consult with, or establish any business competing with TechCorp "
    "SG anywhere in the Asia-Pacific region for a period of 24 months.' No specialized "
    "trade secrets or confidential client lists were accessible to Client C in their "
    "junior role.\n\nOn 2026-03-01, Client C resigned and accepted a job offer as a "
    "Web Developer at a rival Singapore fintech startup. TechCorp SG has issued a "
    "Letter of Demand threatening an interim injunction to enforce Clause 22 and "
    "claim liquidated damages under Clause 23 (S$100,000 fixed penalty).\n\n"
    "Governing Frameworks & Precedents:\n\n"
    "Man Financial (S) Pte Ltd v Wong Bark Chuan David [2008] 1 SLR(R) 663 (Singapore "
    "Court of Appeal test for Restraint of Trade).\n\n"
    "Denka Advantech Pte Ltd v Tan Yuanyuan [2020] 2 SLR 1155 (Penalty rule in "
    "Singapore)."
)


def _base_payload(**overrides) -> LegalCaseFactPayload:
    defaults = dict(
        case_id="rot-test",
        cited_precedent="Man Financial (S) Pte Ltd v Wong Bark Chuan David [2008] 1 SLR(R) 663",
        factual_foreseeability=False,
        proximity_type=ProximityType.NO_PROXIMITY,
        public_policy_negation=False,
        has_exemption_clause=False,
    )
    defaults.update(overrides)
    return LegalCaseFactPayload(**defaults)


def test_restraint_void_when_no_legitimate_proprietary_interest():
    payload = _base_payload(
        has_restraint_of_trade_clause=True,
        has_trade_secrets_or_confidential_info=False,
        restraint_duration_months=24,
        restraint_geography_scope="asia_pacific",
    )
    deduction = run_symbolic_deduction(payload)

    assert deduction["restraint_of_trade"]["clause_present"] is True
    assert deduction["restraint_of_trade"]["void"] is True


def test_restraint_valid_when_legitimate_interest_and_reasonable_scope():
    payload = _base_payload(
        case_id="rot-valid",
        has_restraint_of_trade_clause=True,
        has_trade_secrets_or_confidential_info=True,
        restraint_duration_months=6,
        restraint_geography_scope="singapore",
    )
    deduction = run_symbolic_deduction(payload)

    assert deduction["restraint_of_trade"]["void"] is False


def test_restraint_rule_does_not_leak_into_unrelated_cases():
    """A case with no restraint clause at all must never be flagged void,
    even if an unrelated trade-secret fact happens to be present.
    """
    payload = _base_payload(case_id="rot-unrelated", has_restraint_of_trade_clause=False)
    deduction = run_symbolic_deduction(payload)

    assert deduction["restraint_of_trade"]["clause_present"] is False
    assert deduction["restraint_of_trade"]["void"] is None


def test_penalty_extravagant_relative_to_salary():
    result = check_liquidated_damages_penalty(monthly_salary_sgd=4_500.0, liquidated_damages_sgd=100_000.0)

    assert result["is_extravagant_penalty"] is True
    assert result["clause_enforceable"] is False


def test_penalty_reasonable_relative_to_salary():
    result = check_liquidated_damages_penalty(monthly_salary_sgd=4_500.0, liquidated_damages_sgd=20_000.0)

    assert result["is_extravagant_penalty"] is False
    assert result["clause_enforceable"] is True


def test_techcorp_restraint_of_trade_dispute_end_to_end():
    payload = parse_legal_case_text(TECHCORP_RESTRAINT_TEXT, case_id="techcorp-1")

    # Multi-citation "Governing Frameworks & Precedents:" list correctly split.
    assert payload.cited_precedent == "Man Financial (S) Pte Ltd v Wong Bark Chuan David [2008] 1 SLR(R) 663"
    assert payload.additional_precedents == ["Denka Advantech Pte Ltd v Tan Yuanyuan [2020] 2 SLR 1155"]

    primary_graph = check_precedent_status(payload.cited_precedent)
    additional_graph = [check_precedent_status(c) for c in payload.additional_precedents]
    assert primary_graph["is_good_law"] is True
    assert all(g["is_good_law"] for g in additional_graph)

    # Junior role, no trade secrets, 24-month APAC restraint.
    assert payload.has_restraint_of_trade_clause is True
    assert payload.has_trade_secrets_or_confidential_info is False
    assert payload.restraint_duration_months == 24
    assert payload.restraint_geography_scope == "asia_pacific"
    assert payload.monthly_salary_sgd == 4_500.0
    assert payload.liquidated_damages_sgd == 100_000.0

    deduction = run_symbolic_deduction(payload)
    assert deduction["restraint_of_trade"]["void"] is True

    penalty = check_liquidated_damages_penalty(payload.monthly_salary_sgd, payload.liquidated_damages_sgd)
    assert penalty["is_extravagant_penalty"] is True

    summary = render_legal_advice_summary(
        payload, deduction, None, primary_graph, penalty_check=penalty, additional_graph_results=additional_graph
    )
    assert "restraint of trade clause is **void" in summary
    assert "unenforceable penalty" in summary
    # No tort dimension in a pure employment/restraint dispute - must not
    # introduce Spandeck duty-of-care noise into the verdict.
    assert "Spandeck" not in summary
