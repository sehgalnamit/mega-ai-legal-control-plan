"""End-to-end integration test across neural parsing, graph gate,
symbolic deduction and the limitation-period calculator.
"""
from datetime import date

from core.graph_gate import PrecedentGraph
from core.neural_parser import parse_legal_case_text
from core.procedural_calculators import check_limitation_period
from core.symbolic_engine import run_symbolic_deduction

CASE_TEXT = (
    "The loss was foreseeable and there was physical proximity between the "
    "parties. The defendant relies on an exemption clause in a standard form "
    "contract excluding liability for property damage. There was unequal "
    "bargaining power and no inducement was offered. The contract was breached "
    "on 2010-01-01. Cited precedent: Old State Courts Ruling on Duty of Care."
)


def test_full_pipeline_end_to_end():
    payload = parse_legal_case_text(CASE_TEXT, case_id="pipeline-test")

    graph = PrecedentGraph()
    graph_result = graph.check_precedent_status(payload.cited_precedent)
    assert graph_result["is_good_law"] is False
    assert graph_result["warning"] is not None

    deduction = run_symbolic_deduction(payload)
    assert deduction["spandeck"]["duty_of_care_exists"] is True
    assert deduction["ucta"]["unreasonable_schedule_2"] is True

    assert payload.contract_breach_date == "2010-01-01"
    limitation = check_limitation_period(payload.contract_breach_date, as_of=date(2026, 1, 1))
    assert limitation["is_statute_barred"] is True
