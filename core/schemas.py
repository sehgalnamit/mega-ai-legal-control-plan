"""Pydantic JSON contracts for Neural Semantic Parsing output.

These schemas are the ONLY interface between the neural layer (LLM) and
the rest of the control plane. The LLM populates these fields with
extracted facts only - it never decides legal outcomes.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator


class InjuryType(str, Enum):
    PERSONAL_INJURY_OR_DEATH = "personal_injury_or_death"
    PROPERTY_DAMAGE = "property_damage"
    PURE_ECONOMIC_LOSS = "pure_economic_loss"


class ProximityType(str, Enum):
    PHYSICAL_PROXIMITY = "physical_proximity"
    CIRCUMSTANTIAL_PROXIMITY = "circumstantial_proximity"
    CAUSAL_PROXIMITY = "causal_proximity"
    NO_PROXIMITY = "no_proximity"


class BreachTermType(str, Enum):
    """Contract term classification per RDC Concrete Pte Ltd v Sato Kogyo
    (S) Pte Ltd [2007] 4 SLR(R) 413 - determines the right to terminate.
    """

    CONDITION = "condition"
    WARRANTY = "warranty"
    INNOMINATE_TERM = "innominate_term"


class SafrVerdict(str, Enum):
    """W3C-baggage-compatible tri-state MAS SAFR runtime disposition verdict."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"


class LegalCaseFactPayload(BaseModel):
    """Structured facts extracted from unstructured legal case text.

    Populated exclusively by `core.neural_parser` - never hand-written
    with a legal conclusion baked in.
    """

    case_id: str
    cited_precedent: str
    factual_foreseeability: bool
    proximity_type: ProximityType
    public_policy_negation: bool
    has_exemption_clause: bool
    injury_type: Optional[InjuryType] = None
    bargaining_power_unequal: bool = False
    received_inducement: bool = False
    standard_form_contract: bool = False
    contract_breach_date: Optional[str] = None
    breach_term_type: Optional[BreachTermType] = None
    deprived_substantially_whole_benefit: bool = False
    claim_value_sgd: float = 0.0
    # GovOps attribute: neural-extraction self-reported confidence, used
    # only to risk-gate the pipeline (never to decide a legal outcome).
    extraction_confidence: float = 1.0

    @field_validator("contract_breach_date")
    @classmethod
    def _validate_breach_date(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("contract_breach_date must be in YYYY-MM-DD format") from exc
        return value


class GovOpsAuditRecord(BaseModel):
    """GovOps metadata attached to a chat turn for audit / HITL export."""

    trace_id: Optional[str] = None
    conversation_id: str
    enduser_id: str
    safr_disposition: str
    safr_verdict: SafrVerdict
    total_tokens: int
    total_cost_usd: float
