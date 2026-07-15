"""Tests for textnorm — match keys and token-equivalence matching."""

from __future__ import annotations

from tkdn_finder.textnorm import match_key, parse_tkdn_percent, texts_equivalent


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
