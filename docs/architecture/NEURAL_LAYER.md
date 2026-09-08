# Neural Layer (Perception)

**Files:** [`core/neural_parser.py`](../../core/neural_parser.py),
[`parsers/neural_extractor.py`](../../parsers/neural_extractor.py),
[`core/chat_router.py`](../../core/chat_router.py),
[`core/safety/content_moderation.py`](../../core/safety/content_moderation.py)

## Role

The neural layer is **System 1**: fast, pattern-matching perception. Its
only job is to turn unstructured natural-language text into a small,
typed set of fields. It is architecturally forbidden from ever deciding
a legal outcome, verdict, or recommendation.

| Module | Input | Output | Forbidden from doing |
| --- | --- | --- | --- |
| `core/neural_parser.py` | Raw SG legal case/dispute text | `LegalCaseFactPayload` (see `core/schemas.py`) | Deciding duty of care, clause validity, right to terminate |
| `parsers/neural_extractor.py` | Raw contract text (any jurisdiction) | `Contract` / `Clause` (see `schemas/legal_ontology.py`) | Deciding clause enforceability |
| `core/chat_router.py` | Any chat message | Plain conversational reply, or a routing decision | Ever answering a real legal question itself |
| `core/safety/content_moderation.py` | Any chat message | `ModerationResult` (safe/unsafe + categories) | — (pure safety gate, runs first) |

## Why only ~5 fields?

Per the sample-efficiency rationale in the main [README](../../README.md#validation-why-symbolic-rules--smaller-datasets),
the model is never asked to "learn" statutory logic end-to-end. For a
non-compete clause it only extracts `clause_type`, `duration_months`,
`jurisdiction`, `scope`, and `geography` — five shallow fields that are
easy to get right with a small amount of training/prompting, rather than
millions of examples of full legal reasoning.

## Provider priority (all optional - offline mock always works)

1. **Groq** (`GROQ_API_KEY`) — free tier, OpenAI-compatible endpoint,
   model `llama-3.1-8b-instant`.
2. **OpenAI** (`OPENAI_API_KEY`) — `gpt-4o-mini`.
3. **Anthropic** (`ANTHROPIC_API_KEY`) — `claude-3-5-sonnet-20241022`.
4. **Offline deterministic mock** — keyword/regex extraction, zero API
   keys required, used automatically as the final fallback (and in CI).

Every provider call sets `extraction_confidence` (0–1). This is *only*
used downstream to risk-gate the pipeline (see the GovOps SAFR envelope
in [`core/govops/safr_envelope.py`](../../core/govops/safr_envelope.py))
— it is never treated as a legal judgment.

## Content safety guardrail

Every chat message passes through `check_content_safety()` **before**
any other layer runs. It uses the OpenAI moderation endpoint when
`OPENAI_API_KEY` is set, and always has a deterministic offline
regex-based fallback so unsafe content is blocked even with no API keys
configured (see `tests/test_content_moderation.py`).

## Chat routing

Not every message is a legal case. `core/chat_router.is_legal_case_message()`
is a cheap heuristic classifier (keyword density + message length) that
decides whether a message should go through the full neuro-symbolic
pipeline or receive a generic conversational reply via
`generate_generic_reply()`. The generic path is explicitly instructed
(system prompt) to never state a legal conclusion — if the user
describes a real dispute in a "generic" message, it tells them to
restate it as a case so the deterministic pipeline picks it up.

## Handoff to the next layer

The neural layer's output (`LegalCaseFactPayload` or `Contract`) is a
**closed, validated Pydantic schema** — see
[ONTOLOGY.md](ONTOLOGY.md). It is passed to the
[Knowledge Graph / Deterministic layer](KNOWLEDGE_GRAPH_LAYER.md) for
precedent filtering and calendar math, and to the
[Symbolic layer](SYMBOLIC_LAYER.md) for the actual legal deduction.
