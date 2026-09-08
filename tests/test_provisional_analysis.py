"""Tests for the provisional-analysis fallback (offline path) used when
the domain router flags a case with no deterministic rule coverage.
"""
import os

from core.provisional_analysis import PROVISIONAL_BANNER, generate_provisional_analysis


def test_offline_fallback_always_carries_the_provisional_banner():
    for key in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ.pop(key, None)

    usage: dict = {}
    result = generate_provisional_analysis("A dispute about a defamatory social media post.", usage_sink=usage)

    assert result.startswith(PROVISIONAL_BANNER)
    assert usage["model"] == "offline-no-provisional-analysis"
