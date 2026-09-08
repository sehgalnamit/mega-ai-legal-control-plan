"""Unit tests for the GovOps telemetry stack: tracer, FinOps ledger, SAFR envelope."""
from core.govops.finops import FinOpsLedger, TokenBudgetExceededError
from core.govops.safr_envelope import SafrDisposition, evaluate_safr_envelope
from core.govops.tracer import (
    build_span_tree,
    get_captured_spans,
    inject_traceparent,
    reset_trace_buffer,
    start_root_span,
    start_worker_span,
)
from core.schemas import InjuryType, LegalCaseFactPayload, ProximityType


def test_finops_ledger_tracks_cost_and_tokens():
    ledger = FinOpsLedger(max_token_budget=10_000)
    record = ledger.record("neural_parsing", "gpt-4o-mini", input_tokens=500, output_tokens=150)

    assert record.cost_usd > 0
    assert ledger.consumed_tokens == 650
    assert ledger.total_cost_usd == record.cost_usd


def test_finops_circuit_breaker_trips_over_budget():
    ledger = FinOpsLedger(max_token_budget=100)
    raised = False
    try:
        ledger.record("neural_parsing", "gpt-4o", input_tokens=80, output_tokens=50)
    except TokenBudgetExceededError:
        raised = True
    assert raised


def _payload(**overrides) -> LegalCaseFactPayload:
    defaults = dict(
        case_id="safr-test",
        cited_precedent="Spandeck Engineering v AGC [2007] 4 SLR(R) 100",
        factual_foreseeability=True,
        proximity_type=ProximityType.PHYSICAL_PROXIMITY,
        public_policy_negation=False,
        has_exemption_clause=False,
    )
    defaults.update(overrides)
    return LegalCaseFactPayload(**defaults)


def test_safr_envelope_auto_executes_low_risk_payload():
    result = evaluate_safr_envelope(
        _payload(contract_breach_date="2020-01-01"), extraction_confidence=0.95, claim_value_usd=500.0
    )

    assert result.disposition == SafrDisposition.AUTO_EXECUTE
    assert result.verdict == "ALLOW"


def test_safr_envelope_escalates_personal_injury_payload():
    result = evaluate_safr_envelope(
        _payload(injury_type=InjuryType.PERSONAL_INJURY_OR_DEATH, has_exemption_clause=True),
        extraction_confidence=0.95,
        claim_value_usd=500.0,
    )

    assert result.disposition == SafrDisposition.ESCALATE
    assert result.verdict == "ESCALATE"


def test_safr_envelope_observes_high_value_claim():
    result = evaluate_safr_envelope(_payload(), extraction_confidence=0.9, claim_value_usd=45_000.0)

    assert result.disposition == SafrDisposition.OBSERVE
    assert result.verdict == "ALLOW"
    assert "HIGH_VALUE_CLAIM" in result.risk_flags


def test_safr_envelope_escalates_unmapped_domain():
    result = evaluate_safr_envelope(
        _payload(contract_breach_date="2020-01-01"),
        extraction_confidence=0.95,
        claim_value_usd=500.0,
        is_unmapped_domain=True,
    )

    assert result.disposition == SafrDisposition.ESCALATE
    assert "UNMAPPED_DOMAIN" in result.risk_flags


def test_tracer_emits_root_and_worker_spans_with_w3c_traceparent():
    reset_trace_buffer()
    with start_root_span("conv-1", "lawyer_session_1", "test query") as root_span:
        carrier = inject_traceparent()
        assert "traceparent" in carrier

        with start_worker_span("neural_parsing", "chat", "neural_parser") as worker_span:
            worker_span.set_attribute("gen_ai.usage.input_tokens", 100)

    spans = get_captured_spans()
    tree = build_span_tree(spans)
    names = {row["name"] for row in tree}

    assert "legal_chat_request" in names
    assert "neural_parsing" in names
    assert root_span.get_span_context().trace_id != 0
