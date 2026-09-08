"""Routes a chat turn to either the legal-case neuro-symbolic pipeline or
a generic conversational reply, and provides the generic reply itself.

Kept separate from `core.neural_parser` because generic small talk is
NOT a legal fact-extraction task and must never be pushed through the
symbolic engine - it never states a legal conclusion.

Provider priority for generic replies: Groq (free tier) -> OpenAI ->
Anthropic -> a deterministic offline canned reply.
"""
from __future__ import annotations

import os
import re
from typing import Optional

from core.domain_taxonomy import classify_singapore_legal_domains

_LEGAL_CASE_KEYWORDS = (
    "breach", "contract", "clause", "duty of care", "tort", "damages", "liability",
    "exemption", "warranty", "condition", "lease", "landlord", "tenant", "negligence",
    "terminate", "limitation act", "precedent", "sue", "lawsuit", "dispute", "non-compete",
)

# Word-boundary regexes - plain substring checks would false-positive on
# ordinary words like "approac-HI-ng" or "t-HEY" ("they").
_GREETING_RE = re.compile(r"\b(hello|hi|hey)\b", re.IGNORECASE)
_HELP_RE = re.compile(r"\bhelp\b|what can you do", re.IGNORECASE)

GENERIC_SYSTEM_PROMPT = """You are the Mega AI Singapore Legal Control Plane assistant.
For casual conversation, be brief, friendly, and helpful. You must NEVER
state a legal conclusion, verdict, or advice yourself - if the user
describes a real dispute, tell them to describe the facts so the
deterministic legal pipeline can evaluate it instead.
"""


def is_legal_case_message(text: str) -> bool:
    """Heuristic classifier: does this message describe a legal case/dispute?

    Combines a narrow tort/UCTA/RDC-Concrete keyword list with the full
    13-domain Singapore legal taxonomy (`core.domain_taxonomy`), so cases
    outside the narrow list (e.g. strata/BMSMA, trade secrets, insolvency,
    crypto/fintech) still get routed to the deterministic pipeline instead
    of a generic chat reply - even when no rule module is loaded for them.
    """
    lowered = text.lower()
    hits = sum(1 for kw in _LEGAL_CASE_KEYWORDS if kw in lowered)
    if hits >= 2 or (len(text.split()) > 40 and hits >= 1):
        return True
    return bool(classify_singapore_legal_domains(text))


def generate_generic_reply(message: str, usage_sink: Optional[dict] = None) -> str:
    """Produce a plain conversational reply for non-case chat messages."""
    for env_var, fn in (
        ("GROQ_API_KEY", _groq_reply),
        ("OPENAI_API_KEY", _openai_reply),
        ("ANTHROPIC_API_KEY", _anthropic_reply),
    ):
        api_key = os.getenv(env_var)
        if api_key:
            try:
                return fn(message, api_key, usage_sink)
            except Exception:
                continue

    return _offline_reply(message, usage_sink)


def _offline_reply(message: str, usage_sink: Optional[dict]) -> str:
    if usage_sink is not None:
        usage_sink.update(
            model="offline-canned-reply",
            input_tokens=max(len(message) // 4, 1),
            output_tokens=10,
        )
    lowered = message.lower().strip()
    if _GREETING_RE.search(lowered):
        return (
            "Hello! I'm the Mega AI legal control plane assistant. Describe a dispute "
            "and I'll run it through the deterministic pipeline, or just chat with me."
        )
    if _HELP_RE.search(lowered):
        return (
            "I can chat, or analyze a legal dispute (e.g. a lease/aircon breach, a tort claim, "
            "or a non-compete clause) through a neuro-symbolic pipeline: neural fact extraction, "
            "a precedent graph gate, and a deterministic rule engine."
        )
    return "Got it. Feel free to describe a legal dispute in detail and I'll run the deterministic pipeline on it."


def _chat_completion(
    message: str, api_key: str, base_url: Optional[str], model: str, usage_sink: Optional[dict]
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0.4,
        messages=[
            {"role": "system", "content": GENERIC_SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
    )
    if usage_sink is not None:
        usage = response.usage
        usage_sink.update(
            model=model,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )
    return response.choices[0].message.content


def _groq_reply(message: str, api_key: str, usage_sink: Optional[dict]) -> str:
    return _chat_completion(message, api_key, "https://api.groq.com/openai/v1", "llama-3.1-8b-instant", usage_sink)


def _openai_reply(message: str, api_key: str, usage_sink: Optional[dict]) -> str:
    return _chat_completion(message, api_key, None, "gpt-4o-mini", usage_sink)


def _anthropic_reply(message: str, api_key: str, usage_sink: Optional[dict]) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=512,
        temperature=0.4,
        system=GENERIC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": message}],
    )
    if usage_sink is not None:
        usage = response.usage
        usage_sink.update(
            model="claude-3-5-sonnet-20241022",
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )
    return response.content[0].text
