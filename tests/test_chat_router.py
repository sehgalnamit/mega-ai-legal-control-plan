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


def test_ordinary_words_containing_hi_or_hey_do_not_trigger_greeting_reply():
    """Regression test: 'hi' and 'hey' are substrings of common words like
    'approaching' and 'they' - the greeting detector must use word
    boundaries, not naive substring matching.
    """
    for key in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ.pop(key, None)

    reply = generate_generic_reply("This is approaching the deadline they mentioned.")

    assert "Hello! I'm the Mega AI" not in reply


def test_strata_bmsma_dispute_is_a_legal_case():
    """Regression test: a case entirely outside the narrow tort/UCTA/RDC
    Concrete keyword list must still be routed via the full 13-domain
    taxonomy, not treated as generic chat.
    """
    text = (
        "Client C owns a ground-floor commercial unit in a strata-titled development. "
        "Subsidiary Proprietor D challenges the validity of an EGM resolution, arguing that "
        "BMSMA requires a Special Resolution for granting exclusive use of common property, "
        "and threatens to apply to the Strata Titles Board for an order invalidating the grant."
    )
    assert is_legal_case_message(text) is True


def test_insolvency_clawback_dispute_is_a_legal_case():
    text = (
        "The Liquidator discovered that the company transferred title of a warehouse to its "
        "parent shortly before liquidation, and wants to apply under IRDA to claw back the "
        "warehouse into the liquidation pool."
    )
    assert is_legal_case_message(text) is True
