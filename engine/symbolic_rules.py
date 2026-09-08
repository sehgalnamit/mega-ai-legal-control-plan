"""Deterministic rule engine for the general-purpose legal ontology.

Unlike `core.symbolic_engine` (pyDatalog Horn clauses for SG tort/UCTA),
this module demonstrates the "zero-data rule update" pattern with plain,
auditable Python: statutory limits live in a single rules table that
can be edited directly - no model retraining required - to reflect a
change in the law (e.g. a max non-compete duration dropping from 12 to
6 months).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from schemas.legal_ontology import Clause, ClauseType, Contract, Jurisdiction

# Statutory / precedent-derived limits. Update this table directly when
# the law changes - zero retraining of the neural extractor is required.
NON_COMPETE_MAX_DURATION_MONTHS: Dict[Jurisdiction, Optional[int]] = {
    Jurisdiction.SINGAPORE: 12,
    Jurisdiction.CALIFORNIA: 0,  # California bars post-employment non-competes outright.
    Jurisdiction.NEW_YORK: 12,
    Jurisdiction.UNITED_KINGDOM: 12,
    Jurisdiction.UNSPECIFIED: None,  # unknown jurisdiction - cannot rule deterministically.
}


@dataclass
class RuleResult:
    rule_name: str
    clause_id: str
    outcome: Optional[bool]  # None means "not applicable / cannot be decided"
    rationale: str


def evaluate_non_compete_clause(clause: Clause) -> RuleResult:
    """Deterministically evaluate whether a non-compete clause's duration
    is enforceable in its stated jurisdiction.
    """
    if clause.clause_type != ClauseType.NON_COMPETE:
        return RuleResult(
            rule_name="non_compete_duration_cap",
            clause_id=clause.clause_id,
            outcome=None,
            rationale=f"Clause {clause.clause_id} is not a non-compete clause; rule not applicable.",
        )

    max_months = NON_COMPETE_MAX_DURATION_MONTHS.get(clause.jurisdiction)

    if max_months is None:
        return RuleResult(
            rule_name="non_compete_duration_cap",
            clause_id=clause.clause_id,
            outcome=None,
            rationale=f"No statutory duration cap on file for jurisdiction '{clause.jurisdiction.value}'.",
        )

    if clause.duration_months is None:
        return RuleResult(
            rule_name="non_compete_duration_cap",
            clause_id=clause.clause_id,
            outcome=None,
            rationale="No duration_months extracted from the clause; cannot evaluate.",
        )

    if max_months == 0:
        outcome = False
        rationale = f"Jurisdiction '{clause.jurisdiction.value}' bars non-compete clauses outright."
    else:
        outcome = clause.duration_months <= max_months
        rationale = (
            f"Clause duration {clause.duration_months} months "
            f"{'<=' if outcome else '>'} statutory cap {max_months} months "
            f"for jurisdiction '{clause.jurisdiction.value}'."
        )

    return RuleResult(
        rule_name="non_compete_duration_cap",
        clause_id=clause.clause_id,
        outcome=outcome,
        rationale=rationale,
    )


_CLAUSE_RULES: Dict[ClauseType, Callable[[Clause], RuleResult]] = {
    ClauseType.NON_COMPETE: evaluate_non_compete_clause,
}


def evaluate_contract(contract: Contract) -> List[RuleResult]:
    """Run every applicable deterministic rule against each clause in a contract."""
    results: List[RuleResult] = []
    for clause in contract.clauses:
        rule_fn = _CLAUSE_RULES.get(clause.clause_type)
        if rule_fn is not None:
            results.append(rule_fn(clause))
    return results
