# Ontology Layer

**Files:** [`core/schemas.py`](../../core/schemas.py),
[`schemas/legal_ontology.py`](../../schemas/legal_ontology.py),
[`core/domain_taxonomy.py`](../../core/domain_taxonomy.py),
[`core/data/singapore_legal_domains.json`](../../core/data/singapore_legal_domains.json),
[`audit/proof_tracer.py`](../../audit/proof_tracer.py)

## Role

The ontology is the **shared vocabulary** every other layer is written
against. It is the contract between the neural layer (which populates
it) and the symbolic layer (which reads it) — neither layer can drift
out of sync with the other because both are typed against the same
Pydantic models.

Three ontologies exist side by side, deliberately kept separate:

| Ontology | Scope | Consumed by |
| --- | --- | --- |
| `core/schemas.py` (`LegalCaseFactPayload`) | Singapore tort/UCTA/RDC Concrete/restraint-of-trade/penalty fact payload, plus GovOps audit fields | `core.symbolic_engine`, `app.py` |
| `schemas/legal_ontology.py` (`Contract`, `Clause`, `Entity`, `Obligation`) | Jurisdiction-agnostic contract/clause model | `engine.symbolic_rules`, `parsers.neural_extractor` |
| `core/domain_taxonomy.py` (`SingaporeLegalDomain`) | The full 13-domain Singapore legal matter-type taxonomy (a SALI-style classification, not a fact schema) | `core.domain_taxonomy.classify_singapore_legal_domains`, `app.py`'s unmapped-domain fallback |

This mirrors how real legal-tech ontology projects are structured: a
narrow, statute-specific schema for a shipped product feature, a
broader general-purpose ontology for extensibility, and a top-level
matter-type taxonomy for routing/classification.

## Prior art: Singapore's open-source legal computation ecosystem

This project deliberately does **not** reinvent a full OWL/RDF legal
ontology from scratch. Singapore already has active, open-source
investment in this exact space, which this project is designed to be
pluggable with:

- **[L4](https://github.com/smucclaw) (SMU Centre for Computational Law
  — CCLAW):** a domain-specific language that compiles natural-language
  statutes, regulations, and contracts into formal logic, including
  deontic modalities (`MUST` / `MAY` / `SHANT`) and temporal rules. Our
  `Obligation.modality` field (`schemas/legal_ontology.py`) uses the
  same deontic vocabulary so extracted obligations could, in principle,
  be lowered into L4 rather than (or alongside) the Python rules table
  in `engine/symbolic_rules.py`.
- **SOLID (Singapore Open Legal Informatics Database — SMU / MinLaw):**
  an open empirical dataset of Singapore court decisions, statutes, and
  judicial structures. This is the natural real-world data source to
  seed `core/graph_gate.py`'s precedent hierarchy graph beyond its
  current in-memory demo data.
- **LKIF (Legal Knowledge Interchange Format):** a formal OWL ontology
  for legal concepts, obligations, and rights. A production system
  would map `schemas/legal_ontology.py` classes onto LKIF classes for
  interoperability with other legal-tech tooling.
- **SALI (Standards for Analytics in Legal Tech):** an open industry
  taxonomy for legal matter types, document categories, and clause
  tags. `ClauseType` in `schemas/legal_ontology.py` is intentionally a
  small, extensible enum that could be superseded by SALI's clause
  taxonomy without touching the rule engine's logic. `SingaporeLegalDomain`
  in `core/domain_taxonomy.py` plays the same role at the matter-type
  level: its 13 domains (commercial contract, employment, tort,
  consumer/sale of goods, real estate, corporate, insolvency, IP/tech,
  banking/fintech, family, criminal, public/administrative, procedural)
  are exactly the kind of top-level taxonomy SALI standardizes, and
  `core/data/singapore_legal_domains.json` is the JSON knowledge base
  that could be swapped for a SALI-conformant mapping without touching
  the classifier code.

## Validation: why symbolic rules + smaller datasets

```text
[Small Dataset] ──► [LLM / Small Fine-Tuned Model] ──► [Structured Legal Schema (Ontology)]
                                                                    │
                                                                    ▼
[Statutory Rules / Logic] ───────────────────────────► [Deterministic Rule Engine] ──► [100% Verifiable Verdict]
```

1. **High sample efficiency.** The neural layer only has to learn to
   extract ~5 shallow fields per clause (e.g. `clause_type`,
   `duration_months`, `jurisdiction`, `scope`, `geography`), not
   end-to-end legal reasoning. Field extraction converges with far less
   data than training a model to "learn" non-compete limits directly.
2. **Zero-data rule updates.** When a statute or precedent changes,
   nothing is retrained — the rule table in
   [`engine/symbolic_rules.py`](../../engine/symbolic_rules.py) or the
   Horn clauses in
   [`core/symbolic_engine.py`](../../core/symbolic_engine.py) are edited
   directly, and every future extraction is evaluated against the new
   rule with 100% consistency.
3. **Mathematical precision & auditability.** Because the ontology
   fields are typed and bounded (enums, integers, booleans), the rule
   engine's conditions are exact — no probabilistic guessing at the
   final decision step. `audit/proof_tracer.py` links every rule
   evaluation back to the exact `clause_id` (and `source_line`, when
   known) that produced it, so a verdict is always traceable to its
   source text.

## Handoff to other layers

- Populated by: the [Neural layer](NEURAL_LAYER.md).
- Read (never mutated) by: the [Symbolic layer](SYMBOLIC_LAYER.md) and
  the [Knowledge Graph / Deterministic layer](KNOWLEDGE_GRAPH_LAYER.md).
- Every field the neural layer can populate is enumerated here — the
  symbolic layer can never "invent" a new fact type at runtime; it can
  only apply rules to what the ontology already defines.
- `core/domain_taxonomy.py`'s `DomainInfo.is_covered` flag is the single
  source of truth for which of the 13 domains have a real deterministic
  `rule_module` today vs. which fall through to the
  `UNMAPPED_DOMAIN_PROVISIONAL_ANALYSIS` fallback described in
  [SYMBOLIC_LAYER.md](SYMBOLIC_LAYER.md#domain-routing--open-world-fallback).
