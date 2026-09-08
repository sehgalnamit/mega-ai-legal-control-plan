# Deterministic / Knowledge Graph Layer

**Files:** [`core/graph_gate.py`](../../core/graph_gate.py),
[`core/procedural_calculators.py`](../../core/procedural_calculators.py)

## Role

This layer covers everything that is deterministic but is **not**
expressed as Horn-clause/rule-table legal deduction: precedent context
filtering (graph traversal) and exact calendar arithmetic. Both run
*before or alongside* the symbolic layer, never inside an LLM prompt.

| Module | Function | Guarantee |
| --- | --- | --- |
| `core/graph_gate.py` | `check_precedent_status()` — traverses a *stare decisis* hierarchy (State Courts → SGHC → SGCA) and flags `OVERRULED` precedents | Context filtering only — never decides the case, only whether a cited authority is still good law |
| `core/procedural_calculators.py` | `check_limitation_period()` — Limitation Act 1959 s.6(1)(a) 6-year window from breach date | Exact date arithmetic, not an LLM estimate |
| `core/procedural_calculators.py` | `check_liquidated_damages_penalty()` — Denka Advantech penalty rule: liquidated sum vs. a salary-based proxy for the greatest conceivable loss | Exact numeric comparison, not an open-textured multi-factor test |

## Why "knowledge graph is context, not reasoning"

`core/graph_gate.py` currently uses an in-memory NetworkX `DiGraph` as a
drop-in stand-in for a real Neo4j deployment (same data model — nodes
are citations with a `court` level and `status`, edges are
`OVERRULED_BY` relationships). Its only output is a status dict
(`is_good_law`, `overruled_by`, `warning`) — it never contributes a
legal conclusion itself. If a cited precedent is overruled, the
*warning* is surfaced to the chatbot response, but the case is still
evaluated on its facts; the graph gate's job is disclosure, not
adjudication.

Swapping the NetworkX backend for real Neo4j (or seeding it from
**SOLID**, Singapore's open empirical court-decision dataset — see
[ONTOLOGY.md](ONTOLOGY.md#prior-art-singapores-open-source-legal-computation-ecosystem))
requires no changes to any other layer, because `check_precedent_status()`
already returns the same plain-dict contract regardless of backend.

## Why calendar math is procedural, not symbolic or neural

The Limitation Act calculation is exact date arithmetic
(`breach_date + 6 years`, with leap-year handling) — there is no
ambiguity or judgment involved, so it is implemented as a plain Python
function rather than a Datalog rule or an LLM estimate. This keeps the
symbolic layer focused purely on genuinely open-textured legal
questions (duty of care, clause reasonableness, term classification).

## Handoff to/from other layers

- **Input:** the citation string and breach date extracted by the
  [Neural layer](NEURAL_LAYER.md) (`LegalCaseFactPayload.cited_precedent`,
  `.contract_breach_date`).
- **Output:** consumed directly by `app.py` for the chat response, and
  by the GovOps SAFR envelope (a missing breach date is itself a risk
  flag — see `core/govops/safr_envelope.py`).
- **Does not feed back into** the [Symbolic layer](SYMBOLIC_LAYER.md)'s
  Horn clauses — the graph gate's warning and the limitation check are
  rendered alongside the symbolic verdict, not merged into it, so the
  provenance of each conclusion stays traceable to the layer that
  produced it.
