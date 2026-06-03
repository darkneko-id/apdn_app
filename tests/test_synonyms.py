"""Tests for synonyms.py — query expansion and synonym loading."""

from __future__ import annotations

import json
import sqlite3

import pytest

from tkdn_finder.synonyms import expand_query, load_synonyms


# ---------------------------------------------------------------------------
# expand_query — bare tokens
# ---------------------------------------------------------------------------

class TestExpandQueryBareTokens:
    def test_no_synonyms_returns_token_with_prefix(self) -> None:
        # Last bare token gets '*' prefix for FTS5 prefix matching
        result = expand_query("pump", {})
        assert result == "pump*"

    def test_synonym_expanded_to_or_group(self) -> None:
        synonyms = {"pump": ["pompa"]}
        result = expand_query("pump", synonyms)
        assert "pump" in result
        assert "pompa" in result
        assert " OR " in result

    def test_synonym_group_wrapped_in_parentheses(self) -> None:
        synonyms = {"pump": ["pompa"]}
        result = expand_query("pump", synonyms)
        # Single-token query with synonym: "(pump* OR pompa*)"
        assert result.startswith("(")
        assert result.endswith(")")

    def test_last_token_gets_prefix_star(self) -> None:
        result = expand_query("centrifugal pump", {})
        # Last token "pump" should have * appended
        assert "pump*" in result

    def test_non_last_token_no_prefix_star(self) -> None:
        result = expand_query("centrifugal pump", {})
        # "centrifugal" is not the last token — no star directly on it
        assert "centrifugal*" not in result

    def test_user_typed_star_not_doubled(self) -> None:
        result = expand_query("pump*", {})
        assert "pump**" not in result
        assert "pump*" in result

    def test_hyphenated_token_quoted(self) -> None:
        result = expand_query("x-over", {})
        # Hyphen must be quoted so FTS5 doesn't treat '-' as NOT operator
        assert '"x-over"' in result

    def test_empty_query_returned_unchanged(self) -> None:
        result = expand_query("", {"pump": ["pompa"]})
        assert result == ""

    def test_whitespace_only_query_returned_unchanged(self) -> None:
        result = expand_query("   ", {})
        assert result.strip() == ""


# ---------------------------------------------------------------------------
# expand_query — quoted phrases
# ---------------------------------------------------------------------------

class TestExpandQueryQuotedPhrases:
    def test_quoted_phrase_passed_through_verbatim(self) -> None:
        synonyms = {"gate valve": ["katup gate"]}
        result = expand_query('"gate valve"', synonyms)
        # Quoted phrase goes straight to FTS5 — no synonym expansion
        assert '"gate valve"' in result

    def test_quoted_phrase_not_synonym_expanded(self) -> None:
        synonyms = {"gate valve": ["katup gate"]}
        result = expand_query('"gate valve"', synonyms)
        assert "katup gate" not in result

    def test_mixed_quoted_and_bare_tokens(self) -> None:
        # Quoted phrase is preserved; bare token after it gets synonym expansion
        synonyms = {"valve": ["katup"]}
        result = expand_query('"centrifugal pump" valve', synonyms)
        assert '"centrifugal pump"' in result
        assert "katup" in result


# ---------------------------------------------------------------------------
# expand_query — multi-token synonym matching
# ---------------------------------------------------------------------------

class TestExpandQueryMultiTokenSynonyms:
    def test_multi_token_phrase_synonym_expanded(self) -> None:
        synonyms = {"gate valve": ["katup gate", "katup pintu"]}
        result = expand_query("gate valve", synonyms)
        assert "katup gate" in result or "katup pintu" in result

    def test_multi_token_synonym_consumed_as_unit(self) -> None:
        synonyms = {"gate valve": ["katup gate"]}
        result = expand_query("gate valve", synonyms)
        # Both tokens consumed as one phrase, not expanded separately
        assert "gate AND valve" not in result

    def test_explicit_and_between_parts(self) -> None:
        result = expand_query("pump valve", {})
        # Multiple tokens joined with explicit AND
        assert " AND " in result


# ---------------------------------------------------------------------------
# load_synonyms — DB integration
# ---------------------------------------------------------------------------

class TestLoadSynonyms:
    def test_loads_enabled_synonym(self, db: sqlite3.Connection) -> None:
        db.execute(
            "INSERT INTO synonym (canonical, variants, enabled) VALUES (?, ?, 1)",
            ("pump", json.dumps(["pompa"])),
        )
        db.commit()

        synonyms = load_synonyms(db)

        assert "pump" in synonyms
        assert "pompa" in synonyms["pump"]

    def test_skips_disabled_synonym(self, db: sqlite3.Connection) -> None:
        db.execute(
            "INSERT INTO synonym (canonical, variants, enabled) VALUES (?, ?, 0)",
            ("pump", json.dumps(["pompa"])),
        )
        db.commit()

        synonyms = load_synonyms(db)

        assert "pump" not in synonyms

    def test_corrupt_json_variants_skipped_gracefully(
        self, db: sqlite3.Connection
    ) -> None:
        db.execute(
            "INSERT INTO synonym (canonical, variants, enabled) VALUES (?, ?, 1)",
            ("pump", "not valid json {{{"),
        )
        db.commit()

        synonyms = load_synonyms(db)  # must not raise

        assert "pump" not in synonyms

    def test_non_list_variants_skipped_gracefully(self, db: sqlite3.Connection) -> None:
        db.execute(
            "INSERT INTO synonym (canonical, variants, enabled) VALUES (?, ?, 1)",
            ("pump", json.dumps({"not": "a list"})),
        )
        db.commit()

        synonyms = load_synonyms(db)

        assert "pump" not in synonyms

    def test_empty_synonym_table_returns_empty_dict(
        self, db: sqlite3.Connection
    ) -> None:
        synonyms = load_synonyms(db)
        assert synonyms == {}

    def test_variants_cast_to_strings(self, db: sqlite3.Connection) -> None:
        db.execute(
            "INSERT INTO synonym (canonical, variants, enabled) VALUES (?, ?, 1)",
            ("code", json.dumps([123, 456])),
        )
        db.commit()

        synonyms = load_synonyms(db)

        assert synonyms["code"] == ["123", "456"]
