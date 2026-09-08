"""Tests for the interactive procedural follow-up session helpers."""
from core.chat_session import FOLLOWUP_CHIPS, build_case_context
from core.schemas import LegalCaseFactPayload, ProximityType


def test_followup_chips_are_well_formed():
    assert len(FOLLOWUP_CHIPS) == 3
    for chip in FOLLOWUP_CHIPS:
        assert chip.key
        assert chip.label


def test_build_case_context_includes_all_available_parts():
    payload = LegalCaseFactPayload(
        case_id="case-1",
        cited_precedent="Unspecified Precedent",
        factual_foreseeability=False,
        proximity_type=ProximityType.NO_PROXIMITY,
        public_policy_negation=False,
        has_exemption_clause=False,
    )
    context = build_case_context("Original facts.", "Prior summary.", payload)

    assert "Original facts." in context
    assert "Prior summary." in context
    assert "case-1" in context


def test_build_case_context_handles_missing_parts():
    assert build_case_context(None, None, None) == "No prior case context available."
