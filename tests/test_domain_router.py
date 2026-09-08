"""Tests for the domain router (open-world "unmapped domain" detection)."""
from core.domain_router import build_skipped_deduction_notice, classify_domains, is_unmapped_domain
from core.schemas import BreachTermType, InjuryType, LegalCaseFactPayload, ProximityType


def _minimal_payload(**overrides) -> LegalCaseFactPayload:
    defaults = dict(
        case_id="domain-test",
        cited_precedent="Unspecified Precedent",
        factual_foreseeability=False,
        proximity_type=ProximityType.NO_PROXIMITY,
        public_policy_negation=False,
        has_exemption_clause=False,
    )
    defaults.update(overrides)
    return LegalCaseFactPayload(**defaults)


def test_unmapped_domain_when_no_known_signals_present():
    payload = _minimal_payload()

    assert classify_domains(payload) == []
    assert is_unmapped_domain(payload) is True


def test_tort_domain_detected_via_injury_type():
    payload = _minimal_payload(injury_type=InjuryType.PROPERTY_DAMAGE)

    assert "tort_negligence" in classify_domains(payload)
    assert is_unmapped_domain(payload) is False


def test_multiple_domains_detected_for_restraint_and_penalty_case():
    payload = _minimal_payload(
        has_restraint_of_trade_clause=True,
        monthly_salary_sgd=4500.0,
        liquidated_damages_sgd=100_000.0,
    )
    domains = classify_domains(payload)

    assert "employment_restraint_of_trade" in domains
    assert "liquidated_damages_penalty" in domains
    assert is_unmapped_domain(payload) is False


def test_skipped_deduction_notice_never_mentions_a_fabricated_verdict():
    """Regression test: the unmapped-domain deduction stand-in must be an
    explicit skip notice, never a Spandeck/UCTA-style deduction line.
    """
    notice = build_skipped_deduction_notice(["Insolvency, Restructuring & Debt Recovery"])

    assert notice["engine_status"] == "DYNAMIC_SYNTHESIS_REQUIRED"
    assert len(notice["proof_trace"]) == 1
    assert "skipped" in notice["proof_trace"][0].lower()
    assert "DEDUCE" not in notice["proof_trace"][0]


def test_skipped_deduction_notice_defaults_to_unclassified():
    notice = build_skipped_deduction_notice([])

    assert "Unclassified" in notice["proof_trace"][0]


def test_contract_term_domain_detected_via_breach_term_type():
    payload = _minimal_payload(breach_term_type=BreachTermType.WARRANTY)

    assert "contract_term_breach" in classify_domains(payload)
