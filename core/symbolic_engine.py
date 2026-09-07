"""Declarative symbolic deduction engine using pyDatalog.

Encodes three areas of Singapore law as formal Horn-clause rules:

1. The Spandeck 2-stage duty of care test
   (Spandeck Engineering v AGC [2007] 4 SLR(R) 100).
2. The UCTA 1977 exemption-clause rules (s.2(1) automatic statutory bar
   and Schedule 2 multi-factor reasonableness test).
3. The RDC Concrete contract-term classification test (RDC Concrete Pte
   Ltd v Sato Kogyo (S) Pte Ltd [2007] 4 SLR(R) 413) for the right to
   terminate vs. a damages-only remedy.

No procedural if/else branching or LLM prompting is used to reach a
legal verdict here - only declarative rule evaluation against asserted
facts.
"""
from __future__ import annotations

from typing import Any, Dict, List

from pyDatalog import pyDatalog

from core.schemas import BreachTermType, InjuryType, LegalCaseFactPayload, ProximityType

# Sentinel used to give negated predicates an intensional definition.
# pyDatalog raises "Predicate without definition" when a predicate used
# under `~` (negation as failure) has never been defined by any rule or
# fact. This seed rule never matches a real case_id, so it satisfies
# the resolver without affecting real deductions.
_NEVER = "__never_matches__"

# `pyDatalog.create_terms` injects names into the *caller's* global
# namespace via frame inspection. It must run at module import time
# (not inside a function body) - CPython function frames don't allow
# writes to f_globals to create new local bindings, so calling it
# inside `initialize_symbolic_rules` would leave these names undefined.
pyDatalog.create_terms(
    "Case, Prox, Inj, Term, "
    "foreseeable, proximity_type_fact, policy_negated, "
    "exemption_clause, factor_bargaining, factor_inducement, "
    "factor_standard_form, breach_term_fact, substantial_deprivation, "
    "proximity_established, prima_facie_duty, duty_of_care_exists, "
    "clause_void_ucta_s21, unreasonable_ucta_schedule2, "
    "right_to_terminate, claim_damages"
)


def initialize_symbolic_rules() -> Any:
    """(Re)declare all Horn-clause rules against the module-level terms.

    Must be called after `pyDatalog.clear()` so each deduction run
    starts from a clean rule/fact base.
    """
    # --- SPANDECK 2-STAGE TORT TEST ---
    # Stage 1: factual foreseeability + legal proximity => prima facie duty.
    proximity_established(Case) <= proximity_type_fact(Case, Prox) & (
        Prox != ProximityType.NO_PROXIMITY.value
    )
    prima_facie_duty(Case) <= foreseeable(Case) & proximity_established(Case)
    # Stage 2: prima facie duty stands unless negated by public policy.
    duty_of_care_exists(Case) <= prima_facie_duty(Case) & ~policy_negated(Case)
    policy_negated(Case) <= (Case == _NEVER)  # seed definition for negation

    # --- UCTA 1977 ---
    # Tier 1: automatic statutory bar for death/personal injury exclusions.
    clause_void_ucta_s21(Case) <= exemption_clause(Case, Inj) & (
        Inj == InjuryType.PERSONAL_INJURY_OR_DEATH.value
    )

    # Tier 2: Schedule 2 multi-factor reasonableness test for other losses.
    unreasonable_ucta_schedule2(Case) <= (
        exemption_clause(Case, Inj)
        & (Inj != InjuryType.PERSONAL_INJURY_OR_DEATH.value)
        & factor_bargaining(Case)
        & factor_standard_form(Case)
        & ~factor_inducement(Case)
    )
    factor_inducement(Case) <= (Case == _NEVER)  # seed definition for negation

    # --- RDC CONCRETE CONTRACT TERM CLASSIFICATION ---
    # Only a breach of condition (or an innominate term causing
    # substantial deprivation) gives rise to a right to terminate; any
    # recognized breach still grounds a damages claim.
    right_to_terminate(Case) <= breach_term_fact(Case, Term) & (Term == BreachTermType.CONDITION.value)
    right_to_terminate(Case) <= (
        breach_term_fact(Case, Term)
        & (Term == BreachTermType.INNOMINATE_TERM.value)
        & substantial_deprivation(Case)
    )
    claim_damages(Case) <= breach_term_fact(Case, Term) & (Term != _NEVER)

    return pyDatalog


def run_symbolic_deduction(payload: LegalCaseFactPayload) -> Dict[str, Any]:
    """Assert extracted facts into pyDatalog, run declarative deduction,
    and return the verdict together with a step-by-step symbolic proof
    trace.
    """
    pyDatalog.clear()
    initialize_symbolic_rules()

    case = payload.case_id
    trace: List[str] = []

    # --- Assert Spandeck facts ---
    if payload.factual_foreseeability:
        +foreseeable(case)
        trace.append(f"ASSERT foreseeable('{case}')  # Stage 1: factual foreseeability")

    +proximity_type_fact(case, payload.proximity_type.value)
    trace.append(
        f"ASSERT proximity_type_fact('{case}', '{payload.proximity_type.value}')  # Stage 1: legal proximity"
    )

    if payload.public_policy_negation:
        +policy_negated(case)
        trace.append(f"ASSERT policy_negated('{case}')  # Stage 2: public policy negation raised")

    # --- Assert UCTA facts ---
    if payload.has_exemption_clause and payload.injury_type is not None:
        +exemption_clause(case, payload.injury_type.value)
        trace.append(f"ASSERT exemption_clause('{case}', '{payload.injury_type.value}')")

    if payload.bargaining_power_unequal:
        +factor_bargaining(case)
        trace.append(f"ASSERT factor_bargaining('{case}')")

    if payload.received_inducement:
        +factor_inducement(case)
        trace.append(f"ASSERT factor_inducement('{case}')")

    if payload.standard_form_contract:
        +factor_standard_form(case)
        trace.append(f"ASSERT factor_standard_form('{case}')")

    # --- Assert RDC Concrete facts ---
    if payload.breach_term_type is not None:
        +breach_term_fact(case, payload.breach_term_type.value)
        trace.append(
            f"ASSERT breach_term_fact('{case}', '{payload.breach_term_type.value}')  # RDC Concrete term classification"
        )

    if payload.deprived_substantially_whole_benefit:
        +substantial_deprivation(case)
        trace.append(f"ASSERT substantial_deprivation('{case}')")

    # --- Query deduced predicates (declarative, not procedural) ---
    proximity_ok = bool(proximity_established(case))
    prima_facie = bool(prima_facie_duty(case))
    duty_exists = bool(duty_of_care_exists(case))
    void_s21 = bool(clause_void_ucta_s21(case))
    unreasonable_sch2 = bool(unreasonable_ucta_schedule2(case))
    right_to_terminate_result = bool(right_to_terminate(case))
    claim_damages_result = bool(claim_damages(case))

    trace.append(f"DEDUCE proximity_established('{case}') => {proximity_ok}")
    trace.append(f"DEDUCE prima_facie_duty('{case}') => {prima_facie}")
    trace.append(f"DEDUCE duty_of_care_exists('{case}') => {duty_exists}")
    trace.append(f"DEDUCE clause_void_ucta_s21('{case}') => {void_s21}")
    trace.append(f"DEDUCE unreasonable_ucta_schedule2('{case}') => {unreasonable_sch2}")
    trace.append(f"DEDUCE right_to_terminate('{case}') => {right_to_terminate_result}")
    trace.append(f"DEDUCE claim_damages('{case}') => {claim_damages_result}")

    exemption_enforceable = (
        payload.has_exemption_clause and not void_s21 and not unreasonable_sch2
    )

    return {
        "case_id": case,
        "spandeck": {
            "proximity_established": proximity_ok,
            "prima_facie_duty": prima_facie,
            "duty_of_care_exists": duty_exists,
        },
        "ucta": {
            "clause_void_s2_1": void_s21,
            "unreasonable_schedule_2": unreasonable_sch2,
            "exemption_clause_enforceable": exemption_enforceable,
        },
        "rdc_concrete": {
            "right_to_terminate": right_to_terminate_result,
            "claim_damages": claim_damages_result,
        },
        "proof_trace": trace,
    }
