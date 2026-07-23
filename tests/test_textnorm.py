"""Tests for textnorm — match keys and token-equivalence matching."""

from __future__ import annotations

from tkdn_finder.textnorm import (
    company_key,
    company_search_term,
    match_key,
    normalize_company_name,
    parse_tkdn_percent,
    texts_equivalent,
)


class TestMatchKey:
    def test_whitespace_case_dash_insensitive(self) -> None:
        assert match_key("Dia. 4 1/2 – 13 3/8") == match_key("dia.4 1/2 - 13  3/8")

    def test_empty_and_none(self) -> None:
        assert match_key(None) == ""
        assert match_key("  ") == ""


class TestParseTkdnPercent:
    def test_comma_decimal_and_percent_sign(self) -> None:
        assert parse_tkdn_percent("35,53 %") == 35.53
        assert parse_tkdn_percent("51.47") == 51.47
        assert parse_tkdn_percent("-") is None
        assert parse_tkdn_percent(None) is None


class TestCompanyKey:
    def test_dotted_and_plain_prefix_spellings_are_equal(self) -> None:
        assert (
            company_key("PT Bumi Kaya Steel Industries")
            == company_key("PT. Bumi Kaya Steel Industries")
            == company_key("PT.  BUMI KAYA STEEL INDUSTRIES")
        )

    def test_different_companies_differ(self) -> None:
        assert company_key("PT Baja Utama") != company_key("PT Baja Utama Perkasa")

    def test_empty(self) -> None:
        assert company_key(None) == ""
        assert company_key("") == ""


class TestCompanySearchTerm:
    def test_strips_legal_entity_prefix(self) -> None:
        assert company_search_term("PT Bumi Kaya Steel Industries") == "Bumi Kaya Steel Industries"
        assert company_search_term("PT. Artas Energi Petrogas") == "Artas Energi Petrogas"
        assert company_search_term("CV. Maju Jaya") == "Maju Jaya"

    def test_name_without_prefix_unchanged(self) -> None:
        assert company_search_term("Bumi Kaya Steel") == "Bumi Kaya Steel"

    def test_prefix_only_name_falls_back_to_full_name(self) -> None:
        # Pathological but must not produce an empty query
        assert company_search_term("PT ") == "PT"


class TestNormalizeCompanyName:
    def test_dotted_and_plain_prefix_collapse_to_one(self) -> None:
        canonical = "PT Bumi Kaya Steel"
        assert normalize_company_name("PT. Bumi Kaya Steel") == canonical
        assert normalize_company_name("PT Bumi Kaya Steel") == canonical
        assert normalize_company_name("PT.Bumi Kaya Steel") == canonical
        assert normalize_company_name("PT.  Bumi Kaya Steel") == canonical

    def test_prefix_case_is_normalised(self) -> None:
        assert normalize_company_name("pt. bumi kaya steel") == "PT bumi kaya steel"
        assert normalize_company_name("Pt Bumi Kaya Steel") == "PT Bumi Kaya Steel"

    def test_all_recognised_prefixes(self) -> None:
        assert normalize_company_name("CV. Maju Jaya") == "CV Maju Jaya"
        assert normalize_company_name("UD Sumber Rejeki") == "UD Sumber Rejeki"
        assert normalize_company_name("PD. Karya Baru") == "PD Karya Baru"
        assert normalize_company_name("Fa. Sinar Abadi") == "FA Sinar Abadi"
        assert normalize_company_name("NV Dwi Warna") == "NV Dwi Warna"

    def test_name_without_prefix_only_collapses_whitespace(self) -> None:
        assert normalize_company_name("Bumi  Kaya   Steel") == "Bumi Kaya Steel"

    def test_prefix_fused_into_word_is_not_a_prefix(self) -> None:
        # "PTPN" (Perkebunan Nusantara) must not be treated as a "PT" prefix.
        assert normalize_company_name("PTPN Nusantara") == "PTPN Nusantara"

    def test_prefix_only_name_gains_no_trailing_space(self) -> None:
        assert normalize_company_name("PT.") == "PT"
        assert normalize_company_name("PT ") == "PT"

    def test_empty_and_none(self) -> None:
        assert normalize_company_name(None) is None
        assert normalize_company_name("") == ""


class TestTextsEquivalent:
    def test_abbreviation_pairs_match(self) -> None:
        assert texts_equivalent(
            "Casing API 5CT, Grade N80, Dia. 4 1/2 - 13 3/8 inch",
            "Casing API 5CT, Gr. N80, Diameter 4 1/2 - 13 3/8 inch",
        )

    def test_reordered_tokens_match(self) -> None:
        assert texts_equivalent(
            "Carbon Steel Seamless Casing, Heat Treatment",
            "Heat Treatment - Carbon Steel Seamless Casing",
        )

    def test_extra_differentiating_token_rejects(self) -> None:
        """'Non-Heat Treatment' is a DISTINCT certificate from 'Heat
        Treatment' — the unmatched 'non' token must reject the pair, even
        though fuzzy scorers rate this pair at 97+."""
        assert not texts_equivalent(
            "Carbon Steel Seamless Line Pipe, Heat Treatment API 5L",
            "Carbon Steel Seamless Line Pipe, Non-Heat Treatment API 5L",
        )

    def test_different_words_reject(self) -> None:
        assert not texts_equivalent(
            "Gate Valve Class 150 API 6D", "Ball Valve Class 150 API 6D"
        )

    def test_completely_different_texts_reject(self) -> None:
        assert not texts_equivalent("Pipa Baja ERW SNI 0068", "Kabel Listrik NYY")

    def test_empty_texts_reject(self) -> None:
        assert not texts_equivalent("", "")
        assert not texts_equivalent("Pipa", "")
