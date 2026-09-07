"""Unit tests for the Spandeck 2-stage duty of care deduction."""
from core.schemas import LegalCaseFactPayload, ProximityType
from core.symbolic_engine import run_symbolic_deduction


def _base_payload(**overrides) -> LegalCaseFactPayload:
    defaults = dict(
        case_id="spandeck-test",
        cited_precedent="Spandeck Engineering v AGC [2007] 4 SLR(R) 100",
        factual_foreseeability=True,
        proximity_type=ProximityType.PHYSICAL_PROXIMITY,
        public_policy_negation=False,
        has_exemption_clause=False,
    )
    defaults.update(overrides)
    return LegalCaseFactPayload(**defaults)


def test_duty_of_care_exists_when_foreseeable_and_proximate_and_no_policy_negation():
    payload = _base_payload(case_id="spandeck-pass")
    result = run_symbolic_deduction(payload)

    assert result["spandeck"]["proximity_established"] is True
    assert result["spandeck"]["prima_facie_duty"] is True
    assert result["spandeck"]["duty_of_care_exists"] is True


def test_no_prima_facie_duty_without_foreseeability():
    payload = _base_payload(case_id="spandeck-no-foreseeability", factual_foreseeability=False)
    result = run_symbolic_deduction(payload)

    assert result["spandeck"]["prima_facie_duty"] is False
    assert result["spandeck"]["duty_of_care_exists"] is False


def test_no_proximity_blocks_prima_facie_duty():
    payload = _base_payload(case_id="spandeck-no-proximity", proximity_type=ProximityType.NO_PROXIMITY)
    result = run_symbolic_deduction(payload)

    assert result["spandeck"]["proximity_established"] is False
    assert result["spandeck"]["duty_of_care_exists"] is False


def test_public_policy_negation_defeats_prima_facie_duty():
    payload = _base_payload(case_id="spandeck-policy-negated", public_policy_negation=True)
    result = run_symbolic_deduction(payload)

    assert result["spandeck"]["prima_facie_duty"] is True
    assert result["spandeck"]["duty_of_care_exists"] is False
