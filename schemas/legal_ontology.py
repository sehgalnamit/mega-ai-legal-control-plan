"""General-purpose legal ontology: Contract, Clause, Obligation, Jurisdiction, Entity.

This is a jurisdiction-agnostic domain ontology, independent of any
single statutory regime (unlike `core.schemas`, which models the SG
tort/UCTA fact payload for the chatbot's Singapore pipeline). It exists
so the neural extraction -> symbolic rule pattern generalizes to new
clause types (e.g. non-compete duration limits) without touching the
pyDatalog Singapore tort/UCTA engine in `core/symbolic_engine.py`.

See docs/architecture/ONTOLOGY.md for the design rationale, including
references to prior-art Singapore legal ontology/DSL projects (L4/CCLAW,
SOLID) and international frameworks (LKIF, SALI).
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Jurisdiction(str, Enum):
    SINGAPORE = "singapore"
    CALIFORNIA = "california"
    NEW_YORK = "new_york"
    UNITED_KINGDOM = "united_kingdom"
    UNSPECIFIED = "unspecified"


class ClauseType(str, Enum):
    NON_COMPETE = "non_compete"
    EXEMPTION_OF_LIABILITY = "exemption_of_liability"
    WARRANTY = "warranty"
    CONDITION = "condition"
    CONFIDENTIALITY = "confidentiality"
    TERMINATION = "termination"


class Entity(BaseModel):
    """A natural or legal person party to a contract."""

    entity_id: str
    name: str
    role: str  # e.g. "employer", "employee", "landlord", "tenant"


class Obligation(BaseModel):
    """A single deontic obligation extracted from a clause."""

    obligation_id: str
    holder_entity_id: str
    modality: str  # "MUST" | "MAY" | "SHANT" (deontic logic, cf. L4/CCLAW)
    action: str


class Clause(BaseModel):
    """A single contract clause, reduced to the minimal typed fields
    needed for deterministic rule evaluation - never free-form text
    passed straight to a rule.
    """

    clause_id: str
    source_line: Optional[int] = None
    clause_type: ClauseType
    jurisdiction: Jurisdiction = Jurisdiction.UNSPECIFIED
    duration_months: Optional[int] = None
    scope: Optional[str] = None
    geography: Optional[str] = None
    obligations: List[Obligation] = Field(default_factory=list)
    raw_text: Optional[str] = None


class Contract(BaseModel):
    """A contract as a bundle of clauses between entities."""

    contract_id: str
    parties: List[Entity] = Field(default_factory=list)
    clauses: List[Clause] = Field(default_factory=list)
