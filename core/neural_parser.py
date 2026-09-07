"""Neural semantic parser (System 1).

Restricted purely to semantic fact extraction: turning unstructured
legal case text into a structured `LegalCaseFactPayload`. This module
is strictly FORBIDDEN from deciding legal outcomes, validity, remedies,
or duties of care - all of that is delegated to the declarative
symbolic engine in `core.symbolic_engine`.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from core.schemas import InjuryType, LegalCaseFactPayload, ProximityType

SYSTEM_PROMPT = """You are a Semantic Fact Extraction engine for Singapore legal texts.

STRICT RULES:
1. You extract FACTS ONLY. You never decide legal outcomes, duties,
   validity of clauses, remedies, or liability.
2. You NEVER apply legal tests (e.g. do not decide if a duty of care
   exists, or if a clause is reasonable/void). That is done by a
   separate symbolic reasoning engine.
3. You output ONLY a JSON object matching the LegalCaseFactPayload
   schema. No prose, no explanations, no legal conclusions.
"""


def parse_legal_case_text(case_text: str, case_id: str = "case-001") -> LegalCaseFactPayload:
    """Extract a `LegalCaseFactPayload` from unstructured legal case text.

    Uses OpenAI if `OPENAI_API_KEY` is set, otherwise falls back to a
    deterministic mock extractor so the full pipeline runs offline.
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if api_key:
        try:
            return _openai_extract_facts(case_text, case_id, api_key)
        except Exception:
            # Fall back to the deterministic mock parser on any API failure
            # rather than letting the neural layer silently invent a verdict.
            pass

    return LegalCaseFactPayload(**_mock_extract_facts(case_text, case_id))


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

    breach_match = re.search(r"(\d{4}-\d{2}-\d{2})", case_text)
    contract_breach_date = breach_match.group(1) if breach_match else None

    precedent_match = re.search(r"cited precedent:\s*([^.\n]+)", case_text, re.IGNORECASE)
    cited_precedent = precedent_match.group(1).strip() if precedent_match else "Unspecified Precedent"

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
    }


def _openai_extract_facts(case_text: str, case_id: str, api_key: str) -> LegalCaseFactPayload:
    from openai import OpenAI  # imported lazily so openai stays an optional dependency

    client = OpenAI(api_key=api_key)
    schema_hint = json.dumps(LegalCaseFactPayload.model_json_schema())

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"case_id: {case_id}\n\n"
                    f"JSON schema to fill:\n{schema_hint}\n\n"
                    f"Legal case text:\n{case_text}"
                ),
            },
        ],
    )
    payload_dict = json.loads(response.choices[0].message.content)
    payload_dict.setdefault("case_id", case_id)
    return LegalCaseFactPayload(**payload_dict)
