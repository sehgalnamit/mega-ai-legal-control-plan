"""Tests for the master Singapore legal domain taxonomy (13 domains)
and the UNMAPPED_DOMAIN_PROVISIONAL_ANALYSIS fallback handler.
"""
from core.domain_taxonomy import (
    DOMAIN_TAXONOMY,
    SingaporeLegalDomain,
    build_unmapped_domain_response,
    classify_singapore_legal_domains,
)


def test_all_13_domains_are_defined():
    assert len(list(SingaporeLegalDomain)) == 13


def test_taxonomy_loads_an_entry_for_every_enum_member():
    for domain in SingaporeLegalDomain:
        assert domain in DOMAIN_TAXONOMY
        info = DOMAIN_TAXONOMY[domain]
        assert info.label
        assert len(info.sub_domains) > 0


def test_commercial_contract_and_employment_and_procedural_domains_are_covered():
    # These are the domains with real deterministic rule modules today.
    assert DOMAIN_TAXONOMY[SingaporeLegalDomain.COMMERCIAL_CONTRACT].is_covered is True
    assert DOMAIN_TAXONOMY[SingaporeLegalDomain.EMPLOYMENT_LAW].is_covered is True
    assert DOMAIN_TAXONOMY[SingaporeLegalDomain.TORT_LAW].is_covered is True
    assert DOMAIN_TAXONOMY[SingaporeLegalDomain.PROCEDURAL_JURISDICTION].is_covered is True


def test_family_law_and_criminal_law_are_honestly_uncovered():
    # No deterministic rule module exists for these yet - must not claim otherwise.
    assert DOMAIN_TAXONOMY[SingaporeLegalDomain.FAMILY_LAW].is_covered is False
    assert DOMAIN_TAXONOMY[SingaporeLegalDomain.CRIMINAL_LAW].is_covered is False
    assert DOMAIN_TAXONOMY[SingaporeLegalDomain.FAMILY_LAW].rule_module is None


def test_classify_family_law_dispute():
    text = "Client wishes to file for divorce and dispute division of matrimonial assets under the Women's Charter."
    matches = classify_singapore_legal_domains(text)

    assert any(d.domain == SingaporeLegalDomain.FAMILY_LAW for d in matches)


def test_classify_ip_dispute():
    text = "A competitor registered a confusingly similar trademark, raising passing off and bad faith registration claims."
    matches = classify_singapore_legal_domains(text)

    assert any(d.domain == SingaporeLegalDomain.IP_TECHNOLOGY for d in matches)


def test_classify_criminal_dispute():
    text = "The accused is charged under the Penal Code for criminal breach of trust and cheating."
    matches = classify_singapore_legal_domains(text)

    assert any(d.domain == SingaporeLegalDomain.CRIMINAL_LAW for d in matches)


def test_build_unmapped_domain_response_shape():
    text = "Client wishes to file for divorce and dispute division of matrimonial assets under the Women's Charter."
    matches = classify_singapore_legal_domains(text)
    response = build_unmapped_domain_response(matches, case_id="unmapped-domain-test")

    assert response["status"] == "UNMAPPED_DOMAIN_PROVISIONAL_ANALYSIS"
    assert response["safr_action"] == "ESCALATE_TO_HUMAN"
    assert response["confidence"] == 0.0
    assert "family_law" in response["matched_singapore_domains"]
    assert any("Women's Charter" in code for code in response["matched_statutory_codes"])


def test_build_unmapped_domain_response_handles_no_matches():
    response = build_unmapped_domain_response([], case_id="no-match-test")

    assert response["matched_singapore_domains"] == []
    assert response["matched_statutory_codes"] == []
    assert "Unclassified" in response["message"]
