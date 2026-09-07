"""Neural semantic parser (System 1).

Restricted purely to semantic fact extraction: turning unstructured
legal case text into a structured `LegalCaseFactPayload`. This module
is strictly FORBIDDEN from deciding legal outcomes, validity, remedies,
or duties of care - all of that is delegated to the declarative
symbolic engine in `core.symbolic_engine`.

Supports a live OpenAI or Anthropic endpoint (selected via whichever
API key is present in the environment) with a deterministic offline
mock fallback so the full pipeline always runs without any API keys.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from core.schemas import BreachTermType, InjuryType, LegalCaseFactPayload, ProximityType

MOCK_MODEL_NAME = "mock-offline-parser"

SYSTEM_PROMPT = """You are a Semantic Fact Extraction engine for Singapore legal texts.

STRICT RULES:
1. You extract FACTS ONLY. You never decide legal outcomes, duties,
   validity of clauses, remedies, or liability.
2. You NEVER apply legal tests (e.g. do not decide if a duty of care
   exists, if a clause is reasonable/void, or if a party may terminate).
   That is done by a separate symbolic reasoning engine.
3. You output ONLY a JSON object matching the LegalCaseFactPayload
   schema. No prose, no explanations, no legal conclusions.
4. You MAY include an `extraction_confidence` float (0-1) reflecting how
   confident you are in the factual extraction itself - never a legal
   judgment.
"""


def parse_legal_case_text(
    case_text: str,
    case_id: str = "case-001",
    usage_sink: Optional[dict] = None,
) -> LegalCaseFactPayload:
    """Extract a `LegalCaseFactPayload` from unstructured legal case text.

    Tries a live OpenAI endpoint first, then Anthropic, then falls back
    to a deterministic mock extractor so the pipeline runs offline. If
    `usage_sink` is provided, it is populated with `model`,
    `input_tokens`, and `output_tokens` for GovOps FinOps tracking.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if openai_key:
        try:
            return _openai_extract_facts(case_text, case_id, openai_key, usage_sink)
        except Exception:
            # Fall back rather than letting the neural layer silently
            # invent a verdict when the live endpoint misbehaves.
            pass

    if anthropic_key:
        try:
            return _anthropic_extract_facts(case_text, case_id, anthropic_key, usage_sink)
        except Exception:
            pass

    payload = LegalCaseFactPayload(**_mock_extract_facts(case_text, case_id))
    if usage_sink is not None:
        usage_sink.update(
            model=MOCK_MODEL_NAME,
            input_tokens=max(len(case_text) // 4, 1),
            output_tokens=max(len(payload.model_dump_json()) // 4, 1),
        )
    return payload


def _mock_extract_facts(case_text: str, case_id: str) -> dict:
    """Deterministic keyword-based fallback extractor used when no LLM
    API key is configured, so the pipeline is fully runnable offline.
    """
    text = case_text.lower()

    foreseeable = any(k in text for k in ("foreseeable", "foreseen", "reasonably expected"))

    if "physical" in text and "proximity" in text:
        proximity_type = ProximityType.PHYSICAL_PROXIMITY
    elif "circumstantial" in text:
        proximity_type = ProximityType.CIRCUMSTANTIAL_PROXIMITY
    elif "causal" in text:
        proximity_type = ProximityType.CAUSAL_PROXIMITY
    elif "no proximity" in text or "not proximate" in text:
        proximity_type = ProximityType.NO_PROXIMITY
    else:
        proximity_type = ProximityType.CIRCUMSTANTIAL_PROXIMITY

    public_policy_negation = any(
        k in text for k in ("public policy", "indeterminate liability", "floodgates")
    )

    has_exemption_clause = any(
        k in text for k in ("exemption clause", "exclusion clause", "limitation of liability")
    )

    if "death" in text or "personal injury" in text:
        injury_type: Optional[InjuryType] = InjuryType.PERSONAL_INJURY_OR_DEATH
    elif "property damage" in text or "property loss" in text:
        injury_type = InjuryType.PROPERTY_DAMAGE
    elif "economic loss" in text or "financial loss" in text:
        injury_type = InjuryType.PURE_ECONOMIC_LOSS
    else:
        injury_type = None

    bargaining_power_unequal = any(
        k in text for k in ("unequal bargaining", "no choice but to accept", "take-it-or-leave-it")
    )
    received_inducement = "no inducement" not in text and any(
        k in text for k in ("inducement", "discount", "incentive offered")
    )
    standard_form_contract = any(
        k in text for k in ("standard form", "boilerplate", "non-negotiable terms")
    )

    if "condition" in text and "innominate" not in text:
        breach_term_type: Optional[BreachTermType] = BreachTermType.CONDITION
    elif "warranty" in text:
        breach_term_type = BreachTermType.WARRANTY
    elif "innominate" in text:
        breach_term_type = BreachTermType.INNOMINATE_TERM
    else:
        breach_term_type = None

    deprived_substantially_whole_benefit = any(
        k in text for k in ("deprived", "entire benefit", "whole benefit")
    )

    breach_match = re.search(r"(\d{4}-\d{2}-\d{2})", case_text)
    contract_breach_date = breach_match.group(1) if breach_match else None

    precedent_match = re.search(r"cited precedent:\s*([^.\n]+)", case_text, re.IGNORECASE)
    cited_precedent = precedent_match.group(1).strip() if precedent_match else "Unspecified Precedent"

    claim_match = re.search(r"s\$\s?([\d,]+(?:\.\d+)?)", case_text, re.IGNORECASE)
    claim_value_sgd = float(claim_match.group(1).replace(",", "")) if claim_match else 0.0

    return {
        "case_id": case_id,
        "cited_precedent": cited_precedent,
        "factual_foreseeability": foreseeable,
        "proximity_type": proximity_type,
        "public_policy_negation": public_policy_negation,
        "has_exemption_clause": has_exemption_clause,
        "injury_type": injury_type,
        "bargaining_power_unequal": bargaining_power_unequal,
        "received_inducement": received_inducement,
        "standard_form_contract": standard_form_contract,
        "contract_breach_date": contract_breach_date,
        "breach_term_type": breach_term_type,
        "deprived_substantially_whole_benefit": deprived_substantially_whole_benefit,
        "claim_value_sgd": claim_value_sgd,
        "extraction_confidence": 0.65,
    }


def _schema_prompt(case_text: str, case_id: str) -> str:
    schema_hint = json.dumps(LegalCaseFactPayload.model_json_schema())
    return (
        f"case_id: {case_id}\n\n"
        f"JSON schema to fill:\n{schema_hint}\n\n"
        f"Legal case text:\n{case_text}\n\n"
        "Respond with ONLY the JSON object, no prose."
    )


def _openai_extract_facts(
    case_text: str, case_id: str, api_key: str, usage_sink: Optional[dict]
) -> LegalCaseFactPayload:
    from openai import OpenAI  # imported lazily so openai stays an optional dependency

    model = "gpt-4o-mini"
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _schema_prompt(case_text, case_id)},
        ],
    )
    payload_dict = json.loads(response.choices[0].message.content)
    payload_dict.setdefault("case_id", case_id)
    payload_dict.setdefault("extraction_confidence", 0.9)

    if usage_sink is not None:
        usage = response.usage
        usage_sink.update(
            model=model,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )

    return LegalCaseFactPayload(**payload_dict)


def _anthropic_extract_facts(
    case_text: str, case_id: str, api_key: str, usage_sink: Optional[dict]
) -> LegalCaseFactPayload:
    from anthropic import Anthropic  # imported lazily so anthropic stays an optional dependency

    model = "claude-3-5-sonnet-20241022"
    client = Anthropic(api_key=api_key)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _schema_prompt(case_text, case_id)}],
    )
    raw_text = response.content[0].text
    payload_dict = json.loads(raw_text)
    payload_dict.setdefault("case_id", case_id)
    payload_dict.setdefault("extraction_confidence", 0.9)

    if usage_sink is not None:
        usage = response.usage
        usage_sink.update(
            model=model,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )

    return LegalCaseFactPayload(**payload_dict)
