"""Unit tests for the UCTA 1977 exemption-clause deduction rules."""
from core.schemas import InjuryType, LegalCaseFactPayload, ProximityType
from core.symbolic_engine import run_symbolic_deduction


def _base_payload(**overrides) -> LegalCaseFactPayload:
    defaults = dict(
        case_id="ucta-test",
        cited_precedent="UCTA Test Precedent",
        factual_foreseeability=True,
        proximity_type=ProximityType.PHYSICAL_PROXIMITY,
        public_policy_negation=False,
        has_exemption_clause=True,
    )
    defaults.update(overrides)
    return LegalCaseFactPayload(**defaults)


def test_s2_1_automatically_voids_personal_injury_exclusion():
    payload = _base_payload(
        case_id="ucta-s21-void",
        injury_type=InjuryType.PERSONAL_INJURY_OR_DEATH,
    )
    result = run_symbolic_deduction(payload)

    assert result["ucta"]["clause_void_s2_1"] is True
    assert result["ucta"]["exemption_clause_enforceable"] is False


def test_schedule2_unreasonable_when_unequal_bargaining_and_standard_form_without_inducement():
    payload = _base_payload(
        case_id="ucta-sch2-unreasonable",
        injury_type=InjuryType.PROPERTY_DAMAGE,
        bargaining_power_unequal=True,
        standard_form_contract=True,
        received_inducement=False,
    )
    result = run_symbolic_deduction(payload)

    assert result["ucta"]["clause_void_s2_1"] is False
    assert result["ucta"]["unreasonable_schedule_2"] is True
    assert result["ucta"]["exemption_clause_enforceable"] is False


def test_schedule2_reasonable_when_inducement_offered():
    payload = _base_payload(
        case_id="ucta-sch2-reasonable",
        injury_type=InjuryType.PROPERTY_DAMAGE,
        bargaining_power_unequal=True,
        standard_form_contract=True,
        received_inducement=True,
    )
    result = run_symbolic_deduction(payload)

    assert result["ucta"]["unreasonable_schedule_2"] is False
    assert result["ucta"]["exemption_clause_enforceable"] is True
