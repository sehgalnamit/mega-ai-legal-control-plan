"""Content-safety guardrail applied to every user chat message before it
reaches any LLM or symbolic pipeline stage.

Uses OpenAI's moderation endpoint when an API key is configured, and
always falls back to a deterministic keyword/regex classifier so the
guardrail still runs fully offline with zero external dependencies.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List

# Deterministic offline fallback categories. Not exhaustive - intended
# as a last-resort net, not a replacement for a real moderation API.
_HARMFUL_PATTERNS = {
    "violence": [
        r"\bhow to (?:make|build) a bomb\b",
        r"\bhow (?:do i|to) kill (?:him|her|them|someone)\b",
        r"\bmass shooting\b",
    ],
    "self_harm": [
        r"\bhow (?:do i|to) (?:kill myself|end my life)\b",
        r"\bsuicide method\b",
    ],
    "csam": [r"\bchild (?:sexual|porn)"],
    "weapons_or_drugs": [
        r"\bhow to (?:synthesize|make) (?:meth|sarin|nerve gas)\b",
        r"\bbuy illegal weapons\b",
    ],
    "hate": [r"\ball [a-z]+ people should (?:die|be killed)\b"],
}


@dataclass
class ModerationResult:
    is_safe: bool
    categories: List[str] = field(default_factory=list)
    source: str = "offline_heuristic"


def _offline_check(text: str) -> ModerationResult:
    lowered = text.lower()
    hit_categories = [
        category
        for category, patterns in _HARMFUL_PATTERNS.items()
        if any(re.search(pattern, lowered) for pattern in patterns)
    ]
    return ModerationResult(is_safe=not hit_categories, categories=hit_categories, source="offline_heuristic")


def check_content_safety(text: str) -> ModerationResult:
    """Screen a user message for harmful content before any pipeline stage runs."""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            return _openai_moderation_check(text, api_key)
        except Exception:
            pass  # fall through to the offline heuristic if the API call fails

    return _offline_check(text)


def _openai_moderation_check(text: str, api_key: str) -> ModerationResult:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.moderations.create(model="omni-moderation-latest", input=text)
    result = response.results[0]
    flagged_categories = [category for category, flagged in result.categories.model_dump().items() if flagged]
    return ModerationResult(is_safe=not result.flagged, categories=flagged_categories, source="openai_moderation")
