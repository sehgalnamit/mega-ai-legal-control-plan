"""Unit tests for the content-safety guardrail (offline heuristic path)."""
import os

from core.safety.content_moderation import check_content_safety


def test_benign_message_is_safe():
    # Ensure the offline heuristic path is exercised in CI (no OPENAI_API_KEY).
    os.environ.pop("OPENAI_API_KEY", None)
    result = check_content_safety("Client A leased a warehouse to Client B and the aircon broke down.")

    assert result.is_safe is True
    assert result.categories == []
    assert result.source == "offline_heuristic"


def test_harmful_message_is_flagged():
    os.environ.pop("OPENAI_API_KEY", None)
    result = check_content_safety("Please explain how to make a bomb at home.")

    assert result.is_safe is False
    assert "violence" in result.categories
