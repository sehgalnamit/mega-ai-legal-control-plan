"""Unit tests for the generic/legal-case chat router."""
import os

from core.chat_router import generate_generic_reply, is_legal_case_message


def test_greeting_is_not_a_legal_case():
    assert is_legal_case_message("Hello, how are you today?") is False


def test_aircon_dispute_is_a_legal_case():
    text = (
        "Client A leased a commercial property to Client B under a standard form lease. "
        "Client B stopped paying rent after breach of the exemption clause and wants to "
        "terminate the contract and claim damages."
    )
    assert is_legal_case_message(text) is True


def test_generic_reply_offline_fallback_for_greeting():
    for key in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ.pop(key, None)

    usage: dict = {}
    reply = generate_generic_reply("hello there", usage_sink=usage)

    assert "Mega AI" in reply
    assert usage["model"] == "offline-canned-reply"
