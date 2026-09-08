"""Master taxonomy of Singapore legal domains (the "map" layer).

Loads `core/data/singapore_legal_domains.json` into a typed knowledge
base covering all 13 top-level Singapore legal domains and their
sub-domains. This is deliberately separate from `core.domain_router`
(which tracks *actually implemented* pyDatalog/procedural rule
coverage for the payload fields this repo models today) - this module
is the broader classification/reference layer: it identifies which
Singapore legal domain(s) a case's raw text most plausibly belongs to,
and reports the relevant statutory codes and precedents, regardless of
whether a deterministic rule module exists for it yet.

`is_covered` / `implemented_sub_domains` let the fallback handler
distinguish "we have a deterministic rule for this" from "here are the
statutes/precedents a human reviewer should start from" - honestly,
without pretending every domain is deterministically solved.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

_TAXONOMY_PATH = Path(__file__).parent / "data" / "singapore_legal_domains.json"


class SingaporeLegalDomain(str, Enum):
    COMMERCIAL_CONTRACT = "commercial_contract"
    EMPLOYMENT_LAW = "employment_law"
    TORT_LAW = "tort_law"
    CONSUMER_SALE_OF_GOODS = "consumer_sale_of_goods"
    REAL_ESTATE_PROPERTY = "real_estate_property"
    CORPORATE_LAW = "corporate_law"
    INSOLVENCY_RESTRUCTURING = "insolvency_restructuring"
    IP_TECHNOLOGY = "ip_technology"
    BANKING_FINANCE = "banking_finance"
    FAMILY_LAW = "family_law"
    CRIMINAL_LAW = "criminal_law"
    PUBLIC_ADMIN_LAW = "public_admin_law"
    PROCEDURAL_JURISDICTION = "procedural_jurisdiction"


@dataclass
class SubDomain:
    name: str
    keywords: List[str]
    implemented: bool = False


@dataclass
class DomainInfo:
    domain: SingaporeLegalDomain
    label: str
    statutory_codes: List[str] = field(default_factory=list)
    precedents: List[str] = field(default_factory=list)
    rule_module: Optional[str] = None
    sub_domains: List[SubDomain] = field(default_factory=list)

    @property
    def is_covered(self) -> bool:
        """True if at least one sub-domain has real deterministic rule coverage."""
        return any(sd.implemented for sd in self.sub_domains)

    @property
    def implemented_sub_domains(self) -> List[str]:
        return [sd.name for sd in self.sub_domains if sd.implemented]

    @property
    def uncovered_sub_domains(self) -> List[str]:
        return [sd.name for sd in self.sub_domains if not sd.implemented]


def _load_taxonomy() -> Dict[SingaporeLegalDomain, DomainInfo]:
    raw = json.loads(_TAXONOMY_PATH.read_text(encoding="utf-8"))
    taxonomy: Dict[SingaporeLegalDomain, DomainInfo] = {}
    for entry in raw["domains"]:
        domain = SingaporeLegalDomain(entry["domain"])
        sub_domains = [
            SubDomain(name=sd["name"], keywords=sd["keywords"], implemented=sd.get("implemented", False))
            for sd in entry["sub_domains"]
        ]
        taxonomy[domain] = DomainInfo(
            domain=domain,
            label=entry["label"],
            statutory_codes=entry.get("statutory_codes", []),
            precedents=entry.get("precedents", []),
            rule_module=entry.get("rule_module"),
            sub_domains=sub_domains,
        )
    return taxonomy


DOMAIN_TAXONOMY: Dict[SingaporeLegalDomain, DomainInfo] = _load_taxonomy()


def classify_singapore_legal_domains(raw_text: str) -> List[DomainInfo]:
    """Keyword-classify raw case text against the full 13-domain taxonomy.

    Returns every domain with at least one sub-domain keyword hit,
    ordered as declared in the taxonomy file (most general first).
    """
    text = raw_text.lower()
    matches: List[DomainInfo] = []
    for info in DOMAIN_TAXONOMY.values():
        if any(keyword.lower() in text for sub_domain in info.sub_domains for keyword in sub_domain.keywords):
            matches.append(info)
    return matches


def build_unmapped_domain_response(matched_domains: List[DomainInfo], case_id: str) -> dict:
    """Build the fallback payload for a case with no deterministic rule
    coverage - explicit escalation, never an exception, never a silent
    default to an unrelated rule module (e.g. Spandeck).
    """
    domain_labels = [d.label for d in matched_domains] or ["Unclassified"]
    statutes = sorted({code for d in matched_domains for code in d.statutory_codes})
    precedents = sorted({p for d in matched_domains for p in d.precedents})

    return {
        "status": "UNMAPPED_DOMAIN_PROVISIONAL_ANALYSIS",
        "case_id": case_id,
        "confidence": 0.0,
        "safr_action": "ESCALATE_TO_HUMAN",
        "message": (
            f"No symbolic rule module is loaded for domain(s) {domain_labels}. "
            "Escalated for legal drafting."
        ),
        "matched_singapore_domains": [d.domain.value for d in matched_domains],
        "matched_statutory_codes": statutes,
        "matched_precedents": precedents,
    }
