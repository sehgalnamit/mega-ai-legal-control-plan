"""Auditable proof tracer: links every deterministic rule evaluation back
to its source clause id (and source line, if known) for compliance review.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from engine.symbolic_rules import RuleResult
from schemas.legal_ontology import Contract


@dataclass
class ProofStep:
    step_index: int
    rule_name: str
    clause_id: str
    source_line: Optional[int]
    outcome: Optional[bool]
    rationale: str
    timestamp: str


@dataclass
class ProofTracer:
    """Accumulates an ordered, immutable audit trail for one contract evaluation."""

    steps: List[ProofStep] = field(default_factory=list)

    def record(self, result: RuleResult, source_line: Optional[int] = None) -> ProofStep:
        step = ProofStep(
            step_index=len(self.steps) + 1,
            rule_name=result.rule_name,
            clause_id=result.clause_id,
            source_line=source_line,
            outcome=result.outcome,
            rationale=result.rationale,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.steps.append(step)
        return step

    def trace_contract(self, contract: Contract, results: List[RuleResult]) -> List[ProofStep]:
        """Record a batch of rule results, resolving each clause's source line."""
        line_by_clause = {c.clause_id: c.source_line for c in contract.clauses}
        for result in results:
            self.record(result, source_line=line_by_clause.get(result.clause_id))
        return self.steps

    def to_dict(self) -> Dict[str, Any]:
        return {"proof_steps": [vars(s) for s in self.steps]}
