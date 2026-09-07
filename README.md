# Mega AI — Singapore Neuro-Symbolic Legal Control Plane

A production-grade demonstration of a **true neuro-symbolic AI architecture**
for Singapore common law and statutory compliance reasoning. It strictly
separates:

- **Neural Semantic Parsing** (LLM) — extracts structured facts only, never a legal verdict.
- **Knowledge Graph Context** (Neo4j / NetworkX) — filters out overruled precedents (*stare decisis*) before reasoning.
- **Declarative Symbolic Deduction** (`pyDatalog`) — the *only* component allowed to decide legal outcomes, expressed as formal Horn clauses.
- **Procedural Math** — exact calendar arithmetic for limitation periods.

## Architectural principles

1. **No LLM reasoning.** The LLM (System 1) only performs semantic fact
   parsing into a Pydantic schema. It is forbidden from deciding duty of
   care, validity of clauses, or remedies.
2. **True declarative deduction.** All legal reasoning is executed by
   `pyDatalog` Horn clauses ($A \Leftarrow B \land C$) — not procedural
   `if/else` and not LLM prompting.
3. **Knowledge graph is context, not reasoning.** The precedent graph
   prunes `OVERRULED` judgments from the reasoning context.
4. **Open-textured decomposition (UCTA reasonableness).**
   - Tier 1: UCTA s.2(1) automatically voids exclusions for death/personal injury.
   - Tier 2: UCTA Schedule 2 property/economic-loss exclusions are evaluated via a declarative multi-factor scoring rule.
5. **Spandeck 2-stage tort test.** Encodes *Spandeck Engineering v AGC*
   [2007] 4 SLR(R) 100 as formal Datalog axioms for duty-of-care evaluation.

## Project structure

```text
├── app.py                         # Streamlit interactive control plane UI
├── core/
│   ├── schemas.py                 # Pydantic JSON contracts for neural parsing
│   ├── neural_parser.py           # Mock/OpenAI LLM semantic parser
│   ├── graph_gate.py              # Neo4j/NetworkX precedent hierarchy gate
│   ├── symbolic_engine.py         # pyDatalog declarative engine (Spandeck & UCTA)
│   └── procedural_calculators.py  # Limitation Act 1959 calendar math
└── tests/
    ├── test_spandeck_rules.py     # Unit tests for tort law deduction
    ├── test_ucta_rules.py         # Unit tests for UCTA s.2(1) and Sch 2
    └── test_full_pipeline.py      # End-to-end integration test
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Running the Streamlit dashboard

```powershell
streamlit run app.py
```

The dashboard walks through the 4-stage control plane pipeline:

1. **Input** — raw legal case text + optional contract breach date.
2. **Stage 1 (Neural Parsing)** — extracted JSON Pydantic payload.
3. **Stage 2 (Graph Gate)** — precedent citation validity / stare decisis status.
4. **Stage 3 (Symbolic Reasoning)** — pyDatalog proof trace: duty of care, UCTA void status, limitation expiry.
5. **Stage 4 (Auditable Execution)** — JSON audit log export for human-in-the-loop sign-off.

### Optional: real LLM parsing

By default the neural parser uses a deterministic offline mock extractor.
Set `OPENAI_API_KEY` in the environment to route extraction through OpenAI
instead (the system prompt still forbids the model from making legal
judgments — it only fills the `LegalCaseFactPayload` schema).

## Running tests

```powershell
pytest
```

## Legal disclaimer

This is a technical demonstration only. It does not constitute legal advice
and the sample rules are simplified for illustrative purposes.
