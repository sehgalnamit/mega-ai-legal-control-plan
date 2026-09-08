"""Tests for the multi-turn HITL follow-up fact-patch detector."""
from core.followup_intent import detect_fact_patch


def test_no_patch_detected_for_unrelated_message():
    assert detect_fact_patch("Thanks, that makes sense.") is None


def test_trade_secret_grant_detected():
    patch = detect_fact_patch(
        "What if Client C had access to TechCorp's proprietary source code?"
    )

    assert patch is not None
    assert patch.field_updates["has_trade_secrets_or_confidential_info"] is True


def test_trade_secret_denial_detected():
    patch = detect_fact_patch("Assume Client C had no access to confidential information.")

    assert patch is not None
    assert patch.field_updates["has_trade_secrets_or_confidential_info"] is False


def test_breach_date_change_detected():
    patch = detect_fact_patch("Please change the breach date to 2025-05-01.")

    assert patch is not None
    assert patch.field_updates["contract_breach_date"] == "2025-05-01"


def test_claim_value_change_detected():
    patch = detect_fact_patch("Update the claim value to S$20,000.")

    assert patch is not None
    assert patch.field_updates["claim_value_sgd"] == 20_000.0
