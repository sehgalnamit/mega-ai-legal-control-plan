# Symbolic Layer (Declarative Deduction)

**Files:** [`core/symbolic_engine.py`](../../core/symbolic_engine.py),
[`engine/symbolic_rules.py`](../../engine/symbolic_rules.py)

## Role

The symbolic layer is the **only** component permitted to produce a
legal verdict. It is 100% deterministic: given the same extracted facts,
it always produces the same output, with a full step-by-step proof
trace. There is no LLM involved anywhere in this layer.

Two parallel implementations exist, demonstrating two valid styles of
symbolic reasoning:

| Module | Style | Domain | Used by |
| --- | --- | --- | --- |
| `core/symbolic_engine.py` | `pyDatalog` Horn clauses ($A \Leftarrow B \land C$) | Singapore tort (*Spandeck*), UCTA 1977, contract-term classification (*RDC Concrete*) | `app.py` chatbot pipeline |
| `engine/symbolic_rules.py` | Plain Python + a rules table | Jurisdiction-agnostic clause rules (e.g. non-compete duration caps) | `tests/test_ontology_pipeline.py`, future clause types |

Both are equally "symbolic" — Datalog Horn clauses are simply a more
declarative notation for the same class of deterministic, auditable
logic. Use `pyDatalog` when a rule genuinely benefits from logical
composition/negation across multiple derived predicates (as with the
Spandeck 2-stage test); use a plain rules table when the rule is a
single lookup/threshold check (as with non-compete duration caps).

## Rules encoded today

- **Spandeck 2-stage duty of care test** (*Spandeck Engineering v AGC*
  [2007] 4 SLR(R) 100): foreseeability + proximity → prima facie duty;
  public policy can negate it.
- **UCTA 1977 s.2(1)**: automatic statutory bar on exemption clauses for
  death/personal injury.
- **UCTA 1977 Schedule 2**: multi-factor reasonableness test for
  property/economic-loss exemption clauses.
- **RDC Concrete term classification** (*RDC Concrete Pte Ltd v Sato
  Kogyo (S) Pte Ltd* [2007] 4 SLR(R) 413): only a breach of condition
  (or an innominate term causing substantial deprivation) grounds a
  right to terminate; any recognized breach grounds damages.
- **Man Financial restraint of trade** (*Man Financial (S) Pte Ltd v
  Wong Bark Chuan David* [2008] 1 SLR(R) 663): a two-tier test - a
  restraint clause is void unless (1) a legitimate proprietary interest
  (e.g. trade secrets) exists, and (2) its duration/geographic scope is
  reasonable between the parties. Deliberately scoped so the rule is
  inert unless a restraint clause is actually asserted for that case -
  it never fires "vacuously true" on an unrelated dispute.
- **Denka Advantech penalty rule** (*Denka Advantech Pte Ltd v Tan
  Yuanyuan* [2020] 2 SLR 1155): implemented in
  `core/procedural_calculators.py`, not pyDatalog - a bright-line
  numeric comparison (liquidated sum vs. a salary-based proxy for the
  greatest conceivable loss) is exact arithmetic, not an open-textured
  multi-factor test, so it follows the same "procedural, not symbolic"
  principle as the Limitation Act calculator.
- **Non-compete duration cap** (`engine/symbolic_rules.py`): a per-
  jurisdiction lookup table (Singapore 12 months, California barred
  outright, etc.).

## Zero-data rule updates

Per the validation rationale (see main [README](../../README.md)),
changing the law never requires retraining the neural layer. For
example, to change Singapore's non-compete cap from 12 to 6 months, you
edit one line in `engine/symbolic_rules.py`:

```python
NON_COMPETE_MAX_DURATION_MONTHS: Dict[Jurisdiction, Optional[int]] = {
    Jurisdiction.SINGAPORE: 6,  # was 12
    ...
}
```

No dataset, no fine-tuning, no prompt changes — the next extraction
that produces `duration_months=8` for Singapore is instantaneously and
correctly flagged as unenforceable.

## Handoff from/to other layers

- **Input:** validated ontology objects from the
  [Neural layer](NEURAL_LAYER.md) (`LegalCaseFactPayload` or `Contract`),
  already filtered by the
  [Knowledge Graph / Deterministic layer](KNOWLEDGE_GRAPH_LAYER.md) for
  overruled precedents.
- **Output:** a verdict dict (`spandeck` / `ucta` / `rdc_concrete` in
  `core.symbolic_engine`, or a list of `RuleResult` in
  `engine.symbolic_rules`) plus a proof trace, both of which are fully
  JSON-serializable for the GovOps audit log.
- **Auditability:** every assert/deduce step is recorded — see
  `core/symbolic_engine.run_symbolic_deduction`'s `proof_trace`, and
  `audit/proof_tracer.py` for the ontology-layer equivalent.
