"""End-to-end test for a genuinely out-of-scope dispute (defamation),
verifying the system explicitly flags UNMAPPED_DOMAIN + escalates,
rather than silently returning an empty/all-false verdict.
"""
import os

from core.domain_router import classify_domains, is_unmapped_domain
from core.govops.safr_envelope import SafrDisposition, evaluate_safr_envelope
from core.neural_parser import parse_legal_case_text
from core.provisional_analysis import PROVISIONAL_BANNER, generate_provisional_analysis

DEFAMATION_CASE_TEXT = (
    "Client D published a social media post accusing a business rival of tax fraud "
    "with no supporting evidence. The rival has demanded a public retraction and "
    "S$200,000 in damages for reputational harm."
)


def test_defamation_case_has_no_known_rule_domain():
    payload = parse_legal_case_text(DEFAMATION_CASE_TEXT, case_id="unmapped-1")

    assert classify_domains(payload) == []
    assert is_unmapped_domain(payload) is True


def test_unmapped_domain_escalates_instead_of_silent_false_verdict():
    payload = parse_legal_case_text(DEFAMATION_CASE_TEXT, case_id="unmapped-2")
    unmapped = is_unmapped_domain(payload)

    safr_result = evaluate_safr_envelope(
        payload,
        extraction_confidence=payload.extraction_confidence,
        claim_value_usd=payload.claim_value_sgd,
        is_unmapped_domain=unmapped,
    )

    assert safr_result.disposition == SafrDisposition.ESCALATE
    assert "UNMAPPED_DOMAIN" in safr_result.risk_flags


def test_provisional_analysis_generated_for_unmapped_domain():
    for key in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ.pop(key, None)

    provisional = generate_provisional_analysis(DEFAMATION_CASE_TEXT)

    assert provisional.startswith(PROVISIONAL_BANNER)
