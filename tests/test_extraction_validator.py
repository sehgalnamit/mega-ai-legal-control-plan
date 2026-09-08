"""Unit tests for the neural-extraction consistency validator."""
from core.govops.extraction_validator import validate_extraction_consistency
from core.govops.safr_envelope import SafrDisposition, evaluate_safr_envelope
from core.schemas import BreachTermType, LegalCaseFactPayload, ProximityType


def _payload(**overrides) -> LegalCaseFactPayload:
    defaults = dict(
        case_id="validator-test",
        cited_precedent="RDC Concrete Pte Ltd v Sato Kogyo (S) Pte Ltd [2007] 4 SLR(R) 413",
        factual_foreseeability=False,
        proximity_type=ProximityType.NO_PROXIMITY,
        public_policy_negation=False,
        has_exemption_clause=True,
    )
    defaults.update(overrides)
    return LegalCaseFactPayload(**defaults)


def test_no_contradiction_for_consistent_extraction():
    payload = _payload(breach_term_type=BreachTermType.WARRANTY)
    text = "Clause 18 stating aircon maintenance is a warranty."

    result = validate_extraction_consistency(payload, text)

    assert result.is_consistent is True
    assert result.contradictions == []


def test_flags_condition_label_contradicting_independent_undertaking_text():
    payload = _payload(breach_term_type=BreachTermType.CONDITION)
    text = "Clause 15 states plant maintenance is an independent undertaking and not a condition of tenancy."

    result = validate_extraction_consistency(payload, text)

    assert result.is_consistent is False
    assert any("independent undertaking" in c for c in result.contradictions)


def test_flags_missing_exemption_clause_when_text_references_one():
    payload = _payload(has_exemption_clause=False)
    text = "Clause 12 is a clear exemption clause excluding all liability."

    result = validate_extraction_consistency(payload, text)

    assert result.is_consistent is False


def test_contradiction_forces_safr_escalation():
    payload = _payload(breach_term_type=BreachTermType.CONDITION)
    contradictions = ["Extracted breach_term_type='condition' contradicts express contract language."]

    result = evaluate_safr_envelope(
        payload,
        extraction_confidence=0.95,
        claim_value_usd=100.0,
        extraction_contradictions=contradictions,
    )

    assert result.disposition == SafrDisposition.ESCALATE
    assert "EXTRACTION_CONTRADICTION" in result.risk_flags
