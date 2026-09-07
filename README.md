# Mega AI — Singapore Neuro-Symbolic Legal Control Plane Chatbot

A production-grade demonstration of a **true neuro-symbolic AI architecture**
for Singapore common law and statutory compliance reasoning, wrapped in a
real-time chatbot interface with full **GovOps runtime governance**. It
strictly separates:

- **Neural Semantic Parsing** (LLM) — extracts structured facts only, never a legal verdict.
- **Knowledge Graph Context** (Neo4j / NetworkX) — filters out overruled precedents (*stare decisis*) before reasoning.
- **Declarative Symbolic Deduction** (`pyDatalog`) — the *only* component allowed to decide legal outcomes, expressed as formal Horn clauses.
- **Procedural Math** — exact calendar arithmetic for limitation periods.
- **GovOps Runtime Governance** — OpenTelemetry distributed tracing with W3C `traceparent` propagation, FinOps token/cost tracking with circuit breakers, iteration caps, and a MAS SAFR disposition envelope (`AUTO_EXECUTE` / `OBSERVE` / `ESCALATE` / `DENY`).

## Architectural principles

1. **No LLM reasoning.** The LLM (System 1) only performs semantic fact
   parsing into a Pydantic schema. It is forbidden from deciding duty of
   care, validity of clauses, right to terminate, or remedies.
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
6. **RDC Concrete term classification.** Encodes *RDC Concrete Pte Ltd v
   Sato Kogyo (S) Pte Ltd* [2007] 4 SLR(R) 413 — only a breach of
   condition (or an innominate term causing substantial deprivation)
   grounds a right to terminate; any recognized breach grounds damages.
7. **GovOps containment.** Every chat turn is wrapped in a root
   OpenTelemetry span, propagates W3C trace context to each worker step,
   tracks token spend against a circuit-breaker budget, enforces a hard
   iteration cap per conversation, and risk-gates the extracted payload
   through a MAS SAFR envelope before symbolic deduction runs.

## Project structure

```text
├── app.py                         # Streamlit real-time legal chatbot
├── core/
│   ├── schemas.py                 # Pydantic contracts (facts + GovOps audit record)
│   ├── neural_parser.py           # OpenAI / Anthropic / offline mock fact extractor
│   ├── graph_gate.py               # Neo4j/NetworkX precedent hierarchy gate
│   ├── symbolic_engine.py         # pyDatalog engine (Spandeck, UCTA, RDC Concrete)
│   ├── procedural_calculators.py  # Limitation Act 1959 calendar math
│   ├── response_renderer.py       # Deterministic plain-English verdict formatting
│   └── govops/
│       ├── tracer.py              # OpenTelemetry spans & W3C traceparent propagation
│       ├── finops.py              # Token accounting, cost calc, circuit breaker, iteration cap
│       └── safr_envelope.py       # MAS SAFR runtime disposition (ALLOW/DENY/ESCALATE)
├── deployment/
│   ├── deploy_azure.sh            # Azure Container Apps deployment
│   └── deploy_gcp.sh              # Google Cloud Run deployment
├── Dockerfile
└── tests/
    ├── test_spandeck_rules.py
    ├── test_ucta_rules.py
    ├── test_full_pipeline.py
    ├── test_govops_telemetry.py       # Tracer, FinOps ledger, SAFR envelope
    └── test_aircon_dispute_pipeline.py # End-to-end aircon lease dispute demo
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # optional: add OPENAI_API_KEY / ANTHROPIC_API_KEY
```

## Running the chatbot

```powershell
streamlit run app.py
```

Type a dispute scenario into the chat box (or click **Use sample aircon
dispute** for the built-in commercial lease / VRV aircon breakdown
example). Each turn renders:

1. A plain-English legal advice summary (deterministically templated -
   never LLM-generated prose about the outcome).
2. A **Deterministic Verdict Card** (extracted facts, graph gate result,
   symbolic deduction, limitation check).
3. A **Symbolic Proof Trace** — the exact pyDatalog assert/deduce steps.
4. A **GovOps & Telemetry Panel** — trace ID, W3C `traceparent`, SAFR
   disposition/reasons, per-step token usage & cost, and the captured
   span tree.

A session-wide **audit log** (all turns, verdicts, and telemetry) can be
downloaded as JSON once you check the HITL approval box.

### Optional: real LLM parsing

By default the neural parser uses a deterministic offline mock extractor.
Set `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY` if OpenAI is unset) in the
environment to route extraction through a live LLM instead — the system
prompt still forbids the model from making legal judgments; it only
fills the `LegalCaseFactPayload` schema.

## Running tests

```powershell
pytest
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for local, Azure Container Apps, and
Google Cloud Run deployment steps.

## Legal disclaimer

This is a technical demonstration only. It does not constitute legal advice
and the sample rules are simplified for illustrative purposes.
