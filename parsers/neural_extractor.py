"""Neural perception layer: raw legal text -> `schemas.legal_ontology` entities.

Mirrors `core.neural_parser`'s "facts only, never a verdict" contract,
but targets the general-purpose ontology (Contract/Clause) instead of
the SG tort/UCTA fact payload. Demonstrates the sample-efficient
extraction pattern: the model only needs to extract ~5 fields per
clause (clause_type, duration_months, jurisdiction, scope, geography),
not learn end-to-end legal reasoning.

Tries a free Groq endpoint first, then OpenAI, then Anthropic, then
falls back to a deterministic offline mock extractor.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from schemas.legal_ontology import Clause, ClauseType, Contract, Jurisdiction

SYSTEM_PROMPT = """You are a Semantic Fact Extraction engine for contract clauses.

STRICT RULES:
1. Extract FACTS ONLY: clause_type, jurisdiction, duration_months, scope,
   and geography. Never decide enforceability, validity, or any legal
   outcome - that is done by a separate deterministic rule engine.
2. Output ONLY a JSON object matching the requested schema. No prose.
"""


def extract_contract(raw_text: str, contract_id: str = "contract-001") -> Contract:
    """Extract a `Contract` (parties + clauses) from raw contract text.

    Provider priority: Groq (free tier) -> OpenAI -> Anthropic -> offline
    deterministic mock extractor.
    """
    for env_var, extractor in (
        ("GROQ_API_KEY", _groq_extract),
        ("OPENAI_API_KEY", _openai_extract),
        ("ANTHROPIC_API_KEY", _anthropic_extract),
    ):
        api_key = os.getenv(env_var)
        if api_key:
            try:
                return extractor(raw_text, contract_id, api_key)
            except Exception:
                continue

    return _mock_extract(raw_text, contract_id)


def _mock_extract(raw_text: str, contract_id: str) -> Contract:
    """Deterministic keyword-based fallback so the pipeline runs offline."""
    text = raw_text.lower()

    if any(k in text for k in ("non-compete", "non compete", "noncompete")):
        clause_type = ClauseType.NON_COMPETE
    elif any(k in text for k in ("exemption", "exclusion")):
        clause_type = ClauseType.EXEMPTION_OF_LIABILITY
    elif "warranty" in text:
        clause_type = ClauseType.WARRANTY
    elif "confidential" in text:
        clause_type = ClauseType.CONFIDENTIALITY
    else:
        clause_type = ClauseType.TERMINATION

    if "singapore" in text:
        jurisdiction = Jurisdiction.SINGAPORE
    elif "california" in text:
        jurisdiction = Jurisdiction.CALIFORNIA
    elif "new york" in text:
        jurisdiction = Jurisdiction.NEW_YORK
    elif "united kingdom" in text or re.search(r"\buk\b", text):
        jurisdiction = Jurisdiction.UNITED_KINGDOM
    else:
        jurisdiction = Jurisdiction.UNSPECIFIED

    duration_months: Optional[int] = None
    month_match = re.search(r"(\d+)\s*-?\s*month", text)
    if month_match:
        duration_months = int(month_match.group(1))
    else:
        year_match = re.search(r"(\d+)\s*-?\s*year", text)
        if year_match:
            duration_months = int(year_match.group(1)) * 12

    geography_match = re.search(
        r"within (\d+\s*(?:km|kilometers|miles) of [^,.\n]+)", raw_text, re.IGNORECASE
    )
    geography = geography_match.group(1).strip() if geography_match else None

    scope_match = re.search(r"scope[:\s]+([^.\n]+)", raw_text, re.IGNORECASE)
    scope = scope_match.group(1).strip() if scope_match else None

    clause = Clause(
        clause_id=f"{contract_id}-clause-1",
        source_line=1,
        clause_type=clause_type,
        jurisdiction=jurisdiction,
        duration_months=duration_months,
        scope=scope,
        geography=geography,
        raw_text=raw_text,
    )
    return Contract(contract_id=contract_id, parties=[], clauses=[clause])


def _schema_prompt(raw_text: str, contract_id: str) -> str:
    schema_hint = json.dumps(Contract.model_json_schema())
    return (
        f"contract_id: {contract_id}\n\nJSON schema to fill:\n{schema_hint}\n\n"
        f"Contract text:\n{raw_text}\n\nRespond with ONLY the JSON object, no prose."
    )


def _groq_extract(raw_text: str, contract_id: str, api_key: str) -> Contract:
    from openai import OpenAI  # Groq exposes an OpenAI-compatible chat completions endpoint

    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        temperature=0,
        max_tokens=1200,
        extra_body={"reasoning_effort": "low"},
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _schema_prompt(raw_text, contract_id)},
        ],
    )
    payload_dict = json.loads(response.choices[0].message.content)
    payload_dict.setdefault("contract_id", contract_id)
    return Contract(**payload_dict)


def _openai_extract(raw_text: str, contract_id: str, api_key: str) -> Contract:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _schema_prompt(raw_text, contract_id)},
        ],
    )
    payload_dict = json.loads(response.choices[0].message.content)
    payload_dict.setdefault("contract_id", contract_id)
    return Contract(**payload_dict)


def _anthropic_extract(raw_text: str, contract_id: str, api_key: str) -> Contract:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _schema_prompt(raw_text, contract_id)}],
    )
    payload_dict = json.loads(response.content[0].text)
    payload_dict.setdefault("contract_id", contract_id)
    return Contract(**payload_dict)
