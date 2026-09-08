"""End-to-end integration test for the aircon maintenance dispute scenario,
exercising the full GovOps telemetry stack (tracing, FinOps, SAFR envelope)
alongside neural parsing, the graph gate, and symbolic deduction.
"""
from datetime import date

from core.govops.finops import FinOpsLedger
from core.govops.safr_envelope import SafrDisposition, evaluate_safr_envelope
from core.govops.tracer import (
    build_span_tree,
    get_captured_spans,
    reset_trace_buffer,
    start_root_span,
    start_worker_span,
)
from core.neural_parser import parse_legal_case_text
from core.procedural_calculators import check_limitation_period
from core.symbolic_engine import run_symbolic_deduction

AIRCON_DISPUTE_TEXT = (
    "Client A leased a commercial property to Client B under a standard form lease "
    "with unequal bargaining power. Client B stopped paying rent because the main "
    "VRV central aircon system broke down in June 2024, causing S$45,000 in spoiled "
    "perishable inventory and severe heat discomfort. The lease contains Clause 14, "
    "a standard form exemption clause, excluding all landlord liability for property "
    "damage caused by equipment breakdown, and Clause 18 stating aircon maintenance "
    "is a warranty. No inducement was offered for these terms. Client B wants to "
    "terminate the lease immediately and claim damages. The contract was breached on "
    "2024-06-15. Cited precedent: RDC Concrete Pte Ltd v Sato Kogyo (S) Pte Ltd "
    "[2007] 4 SLR(R) 413."
)


def test_aircon_dispute_end_to_end_with_govops_telemetry():
    reset_trace_buffer()
    ledger = FinOpsLedger(max_token_budget=20_000)

    with start_root_span("conv-aircon-1", "lawyer_session_1", AIRCON_DISPUTE_TEXT):
        usage_sink: dict = {}
        with start_worker_span("neural_parsing", "chat", "neural_parser"):
            payload = parse_legal_case_text(
                AIRCON_DISPUTE_TEXT, case_id="AIRCON_DISPUTE_2026", usage_sink=usage_sink
            )
            ledger.record(
                "neural_parsing",
                usage_sink.get("model", "mock-offline-parser"),
                usage_sink.get("input_tokens", 0),
                usage_sink.get("output_tokens", 0),
            )

        with start_worker_span("symbolic_deduction", "execute_tool", "symbolic_engine"):
            deduction = run_symbolic_deduction(payload)

        with start_worker_span("limitation_calculator", "execute_tool", "procedural_calculator"):
            limitation = check_limitation_period(payload.contract_breach_date, as_of=date(2026, 1, 1))

    safr_result = evaluate_safr_envelope(
        payload,
        extraction_confidence=payload.extraction_confidence,
        claim_value_usd=payload.claim_value_sgd,
    )

    # Neural parser (System 1) facts only - no legal conclusions.
    assert payload.breach_term_type is not None
    assert payload.breach_term_type.value == "warranty"
    assert payload.claim_value_sgd == 45_000.0
    assert payload.contract_breach_date == "2024-06-15"

    # RDC Concrete: warranty breach => no termination right, damages available.
    assert deduction["rdc_concrete"]["right_to_terminate"] is False
    assert deduction["rdc_concrete"]["claim_damages"] is True

    # UCTA Sch 2: unequal bargaining + standard form + no inducement => unreasonable.
    assert deduction["ucta"]["unreasonable_schedule_2"] is True
    assert deduction["ucta"]["exemption_clause_enforceable"] is False

    # Limitation Act 1959 s.6(1)(a): 6 years from 2024-06-15.
    assert limitation["is_statute_barred"] is False
    assert limitation["limitation_expiry_date"] == "2030-06-15"

    # MAS SAFR: high-value claim (S$45,000) + mock-parser confidence (0.65, below
    # the 0.7 offline-parser threshold) => ESCALATE for human review, not
    # silently auto-executed.
    assert safr_result.disposition == SafrDisposition.ESCALATE
    assert safr_result.verdict == "ESCALATE"

    spans = get_captured_spans()
    tree = build_span_tree(spans)
    names = {row["name"] for row in tree}
    assert {"legal_chat_request", "neural_parsing", "symbolic_deduction", "limitation_calculator"} <= names
