"""Tests for the provisional-analysis fallback (offline path) used when
the domain router flags a case with no deterministic rule coverage.
"""
import os

import pytest

from core.provisional_analysis import (
    PROCEDURAL_FOLLOWUP_BANNER,
    PROVISIONAL_BANNER,
    generate_procedural_followup,
    generate_provisional_analysis,
)


def test_offline_fallback_always_carries_the_provisional_banner():
    for key in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ.pop(key, None)

    usage: dict = {}
    result = generate_provisional_analysis("A dispute about a defamatory social media post.", usage_sink=usage)

    assert result.startswith(PROVISIONAL_BANNER)
    assert usage["model"] == "offline-no-provisional-analysis"


def test_procedural_followup_offline_fallback_carries_its_own_banner():
    for key in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ.pop(key, None)

    usage: dict = {}
    result = generate_procedural_followup("draft_filing", "Some prior case context.", usage_sink=usage)

    assert result.startswith(PROCEDURAL_FOLLOWUP_BANNER)
    assert usage["model"] == "offline-no-provisional-analysis"


def test_procedural_followup_rejects_unknown_task_key():
    with pytest.raises(ValueError):
        generate_procedural_followup("not_a_real_task", "context")
