"""Regression test: "time is of the essence" must be recognized as a
contractual CONDITION (RDC Concrete), and the microchip supply-contract
test case must resolve deterministically rather than falling through
as an unmapped/unclassified domain.
"""
from core.domain_router import classify_domains, is_unmapped_domain
from core.neural_parser import parse_legal_case_text
from core.schemas import BreachTermType
from core.symbolic_engine import run_symbolic_deduction

MICROCHIP_SUPPLY_CASE_TEXT = (
    "Client M entered into a supply agreement on 2025-10-01 with Vendor N to procure 50,000 specialized "
    "microchips for S$1,200,000, payable upon delivery. Clause 4 of the contract states: 'Time of delivery "
    "is of the essence. Delivery must occur no later than 2026-03-01.' Vendor N failed to deliver the "
    "microchips by the deadline and only tendered delivery on 2026-04-15. Client M refused acceptance, "
    "terminated the contract immediately, and sourced alternative chips at a cost of S$1,600,000. Vendor N "
    "sues Client M for wrongful termination, arguing that a 6-week delay in supply chain operations does not "
    "justify contract termination. Client M seeks to affirm the termination and recover S$400,000 in market "
    "cover damages."
)


def test_time_of_the_essence_is_classified_as_a_condition():
    payload = parse_legal_case_text(MICROCHIP_SUPPLY_CASE_TEXT, case_id="microchip-1")

    assert payload.breach_term_type == BreachTermType.CONDITION
    assert classify_domains(payload) == ["contract_term_breach"]
    assert is_unmapped_domain(payload) is False


def test_time_of_the_essence_breach_grounds_termination_and_damages():
    payload = parse_legal_case_text(MICROCHIP_SUPPLY_CASE_TEXT, case_id="microchip-2")
    deduction = run_symbolic_deduction(payload)

    assert deduction["rdc_concrete"]["right_to_terminate"] is True
    assert deduction["rdc_concrete"]["claim_damages"] is True
