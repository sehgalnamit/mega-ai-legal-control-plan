"""End-to-end test for the general-purpose ontology pipeline:
parsers.neural_extractor -> engine.symbolic_rules -> audit.proof_tracer.

Demonstrates the non-compete duration example from the architecture
rationale: Singapore caps non-compete duration at 12 months, California
bars them outright.
"""
from audit.proof_tracer import ProofTracer
from engine.symbolic_rules import evaluate_contract
from parsers.neural_extractor import extract_contract


def test_singapore_non_compete_within_cap_is_enforceable():
    text = (
        "This employment agreement includes a non-compete clause for a duration of "
        "6 months, governed by Singapore law. Scope: software engineering roles."
    )
    contract = extract_contract(text, contract_id="nc-sg-ok")
    results = evaluate_contract(contract)

    assert len(results) == 1
    assert results[0].outcome is True

    tracer = ProofTracer()
    tracer.trace_contract(contract, results)
    assert len(tracer.steps) == 1
    assert tracer.steps[0].clause_id == contract.clauses[0].clause_id
    assert tracer.steps[0].source_line == contract.clauses[0].source_line


def test_singapore_non_compete_exceeding_cap_is_unenforceable():
    text = (
        "This employment agreement includes a non-compete clause for a duration of "
        "24 months, governed by Singapore law."
    )
    contract = extract_contract(text, contract_id="nc-sg-fail")
    results = evaluate_contract(contract)

    assert results[0].outcome is False


def test_california_non_compete_is_barred_outright():
    text = "This agreement includes a non-compete clause for a duration of 3 months in California."
    contract = extract_contract(text, contract_id="nc-ca")
    results = evaluate_contract(contract)

    assert results[0].outcome is False
    assert "bars non-compete" in results[0].rationale
