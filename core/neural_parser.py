"""Neural semantic parser (System 1).

Restricted purely to semantic fact extraction: turning unstructured
legal case text into a structured `LegalCaseFactPayload`. This module
is strictly FORBIDDEN from deciding legal outcomes, validity, remedies,
or duties of care - all of that is delegated to the declarative
symbolic engine in `core.symbolic_engine`.

Provider priority: Groq (free tier, OpenAI-compatible endpoint) ->
OpenAI -> Anthropic -> a deterministic offline mock fallback, so the
full pipeline always runs without any API keys.
"""
from __future__ import annotations

import json
import os
import re
from typing import List, Optional, Tuple

from core.schemas import BreachTermType, InjuryType, LegalCaseFactPayload, ProximityType

MOCK_MODEL_NAME = "mock-offline-parser"

# Matches a case citation of the form "Name v Name [year] Reporter ..." on a
# single line, used as a fallback when no explicit "Cited precedent:" label
# is present (e.g. a "Governing Frameworks & Precedents:" list).
_CASE_CITATION_RE = re.compile(r"([A-Z][\w.&'()\-,\s]*? v\.? [A-Z][\w.&'()\-,\s]*? \[\d{4}\][^\n]*)")
# Strips a trailing explanatory parenthetical, e.g. "... 663 (SGCA test for X)."
_TRAILING_EXPLANATION_RE = re.compile(r"\s*\([^()]*\)\.?\s*$")

# Currency amounts written as "S$2.8 million" / "S$100k" etc. - a bare
# digit regex would parse "2.8 million" as 2.8, silently understating the
# amount by a factor of a million.
_CURRENCY_MULTIPLIERS = {
    "million": 1_000_000,
    "mil": 1_000_000,
    "m": 1_000_000,
    "thousand": 1_000,
    "k": 1_000,
}
_CURRENCY_SUFFIX_PATTERN = r"(million|thousand|mil|m|k)?"

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

    Tries a live Groq endpoint first (free tier), then OpenAI, then
    Anthropic, then falls back to a deterministic mock extractor so the
    pipeline runs offline. If `usage_sink` is provided, it is populated
    with `model`, `input_tokens`, and `output_tokens` for GovOps FinOps
    tracking.
    """
    groq_key = os.getenv("GROQ_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if groq_key:
        try:
            return _groq_extract_facts(case_text, case_id, groq_key, usage_sink)
        except Exception:
            pass

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


def _parse_currency_amount(text: str, label_pattern: str) -> Optional[float]:
    """Extract an `S$<amount>[ million|thousand|m|k]` figure near `label_pattern`.

    e.g. "S$2.8 Million" -> 2_800_000.0, not the bare 2.8 a naive digit
    regex would return.
    """
    pattern = rf"{label_pattern}[^.\n]*?s\$\s?([\d,]+(?:\.\d+)?)\s*{_CURRENCY_SUFFIX_PATTERN}\b"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    amount = float(match.group(1).replace(",", ""))
    multiplier = _CURRENCY_MULTIPLIERS.get((match.group(2) or "").lower(), 1)
    return amount * multiplier


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

    if "innominate" not in text and ("condition" in text or "of the essence" in text):
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

    has_restraint_of_trade_clause = any(
        k in text
        for k in ("restraint of trade", "non-compete", "non compete", "noncompete", "competing business")
    )

    has_trade_secrets_or_confidential_info = has_restraint_of_trade_clause and (
        any(k in text for k in ("trade secret", "confidential client", "confidential information", "client relationships"))
        and not any(
            neg in text
            for neg in ("no trade secret", "no specialized trade secret", "no confidential", "not accessible", "no access to")
        )
    )

    restraint_duration_months: Optional[int] = None
    restraint_geography_scope: Optional[str] = None
    if has_restraint_of_trade_clause:
        restraint_month_match = re.search(r"(\d+)\s*-?\s*month", text)
        if restraint_month_match:
            restraint_duration_months = int(restraint_month_match.group(1))

        if re.search(r"asia[- ]pacific", text):
            restraint_geography_scope = "asia_pacific"
        elif any(k in text for k in ("worldwide", "global")):
            restraint_geography_scope = "global"
        elif "singapore" in text:
            restraint_geography_scope = "singapore"

    monthly_salary_sgd = _parse_currency_amount(case_text, r"monthly salary")

    liquidated_damages_sgd = _parse_currency_amount(case_text, r"(?:liquidated damages|fixed penalty)")

    has_insolvency_clawback_claim = any(
        k in text
        for k in ("claw back", "clawback", "transaction at an undervalue", "irda", "voidable transaction", "unfair preference")
    )

    asset_market_value_sgd: Optional[float] = None
    consideration_paid_sgd: Optional[float] = None
    is_connected_person = False
    transaction_date: Optional[str] = None
    winding_up_date: Optional[str] = None
    if has_insolvency_clawback_claim:
        asset_market_value_sgd = _parse_currency_amount(case_text, r"worth")
        # Allows descriptive words between "for" and the amount, e.g.
        # "for a nominal consideration of S$100,000", not just "for S$100,000".
        for_match = re.search(
            rf"\bfor\b[^.\n]{{0,40}}?s\$\s?([\d,]+(?:\.\d+)?)\s*{_CURRENCY_SUFFIX_PATTERN}\b",
            case_text,
            re.IGNORECASE,
        )
        if for_match:
            for_multiplier = _CURRENCY_MULTIPLIERS.get((for_match.group(2) or "").lower(), 1)
            consideration_paid_sgd = float(for_match.group(1).replace(",", "")) * for_multiplier

        is_connected_person = any(
            k in text
            for k in ("% parent", "wholly-owned", "wholly owned", "connected person", "related party", "associate company")
        )

        winding_up_match = re.search(r"wound up on (\d{4}-\d{2}-\d{2})", text)
        winding_up_date = winding_up_match.group(1) if winding_up_match else None

        all_dates = re.findall(r"\d{4}-\d{2}-\d{2}", case_text)
        remaining_dates = [d for d in all_dates if d != winding_up_date]
        transaction_date = remaining_dates[0] if remaining_dates else None

    has_harassment_claim = any(
        k in text for k in ("harassment", "poha", "protection from harassment", "harasser")
    )
    publishes_identifying_information = has_harassment_claim and any(
        k in text
        for k in ("doxx", "residential address", "home address", "phone number", "personal information", "identifying information")
    )
    urges_third_party_harassment = has_harassment_claim and any(
        k in text for k in ("urged", "urging", "incit", "encouraged others", "subscribers to")
    )
    causes_alarm_distress_or_fear = has_harassment_claim and any(
        k in text for k in ("alarm", "distress", "fear", "afraid")
    )

    breach_match = re.search(r"(\d{4}-\d{2}-\d{2})", case_text)
    contract_breach_date = breach_match.group(1) if breach_match else None

    cited_precedent, additional_precedents = _extract_precedents(case_text)

    claim_match = re.search(
        rf"s\$\s?([\d,]+(?:\.\d+)?)\s*{_CURRENCY_SUFFIX_PATTERN}\b", case_text, re.IGNORECASE
    )
    if claim_match:
        claim_multiplier = _CURRENCY_MULTIPLIERS.get((claim_match.group(2) or "").lower(), 1)
        claim_value_sgd = float(claim_match.group(1).replace(",", "")) * claim_multiplier
    else:
        claim_value_sgd = 0.0

    return {
        "case_id": case_id,
        "cited_precedent": cited_precedent,
        "additional_precedents": additional_precedents,
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
        "has_restraint_of_trade_clause": has_restraint_of_trade_clause,
        "has_trade_secrets_or_confidential_info": has_trade_secrets_or_confidential_info,
        "restraint_duration_months": restraint_duration_months,
        "restraint_geography_scope": restraint_geography_scope,
        "monthly_salary_sgd": monthly_salary_sgd,
        "liquidated_damages_sgd": liquidated_damages_sgd,
        "has_insolvency_clawback_claim": has_insolvency_clawback_claim,
        "asset_market_value_sgd": asset_market_value_sgd,
        "consideration_paid_sgd": consideration_paid_sgd,
        "is_connected_person": is_connected_person,
        "transaction_date": transaction_date,
        "winding_up_date": winding_up_date,
        "has_harassment_claim": has_harassment_claim,
        "publishes_identifying_information": publishes_identifying_information,
        "urges_third_party_harassment": urges_third_party_harassment,
        "causes_alarm_distress_or_fear": causes_alarm_distress_or_fear,
        "extraction_confidence": 0.65,
    }


def _extract_case_citations(raw_text: str) -> List[str]:
    """Scan for bare `Name v Name [year] Reporter` citations (no explicit
    "Cited precedent:" label), stripping a trailing explanatory parenthetical.
    """
    citations = []
    for match in _CASE_CITATION_RE.finditer(raw_text):
        candidate = match.group(1).strip()
        cleaned = _TRAILING_EXPLANATION_RE.sub("", candidate).strip().rstrip(".")
        if cleaned:
            citations.append(cleaned)
    return citations


def _extract_precedents(raw_text: str) -> Tuple[str, List[str]]:
    """Return (primary_citation, additional_citations).

    Prefers an explicit "Cited precedent: X." label; falls back to
    scanning for bare case citations (e.g. a "Governing Frameworks &
    Precedents:" list citing multiple authorities).
    """
    labeled_match = re.search(r"cited precedent:\s*([^.\n]+)", raw_text, re.IGNORECASE)
    if labeled_match:
        return labeled_match.group(1).strip(), []

    citations = _extract_case_citations(raw_text)
    if citations:
        return citations[0], citations[1:]

    return "Unspecified Precedent", []


def _schema_prompt(case_text: str, case_id: str) -> str:
    schema_hint = json.dumps(LegalCaseFactPayload.model_json_schema())
    return (
        f"case_id: {case_id}\n\n"
        f"JSON schema to fill:\n{schema_hint}\n\n"
        f"Legal case text:\n{case_text}\n\n"
        "Respond with ONLY the JSON object, no prose."
    )


def _groq_extract_facts(
    case_text: str, case_id: str, api_key: str, usage_sink: Optional[dict]
) -> LegalCaseFactPayload:
    """Free-tier LLM endpoint: Groq exposes an OpenAI-compatible chat API."""
    from openai import OpenAI  # imported lazily so openai stays an optional dependency

    model = "openai/gpt-oss-20b"
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=1200,
        extra_body={"reasoning_effort": "low"},
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _schema_prompt(case_text, case_id)},
        ],
    )
    payload_dict = json.loads(response.choices[0].message.content)
    payload_dict.setdefault("case_id", case_id)
    payload_dict.setdefault("extraction_confidence", 0.85)

    if usage_sink is not None:
        usage = response.usage
        usage_sink.update(
            model=model,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )

    return LegalCaseFactPayload(**payload_dict)


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
