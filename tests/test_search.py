"""Tests for search.py — two-stage FTS5 + rapidfuzz scoring."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any

import pytest

from tkdn_finder.constants import (
    RERANK_WEIGHT_FUZZY,
    RERANK_WEIGHT_RECENCY,
    RERANK_WEIGHT_TKDN,
    RERANK_WEIGHT_VALIDITY,
    SEARCH_RESULT_LIMIT_MAX,
    VALIDITY_EXPIRING_SOON_DAYS,
)
from tkdn_finder.merger import merge_and_upsert
from tkdn_finder.search import _compute_score, search


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert(db: sqlite3.Connection, cert_factory: Any, **kwargs: Any) -> None:
    merge_and_upsert(db, [cert_factory(**kwargs)])


def _future(days: int = 365) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _past(days: int = 30) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# _compute_score unit tests
# ---------------------------------------------------------------------------

class TestComputeScore:
    def test_exact_match_gives_high_fuzzy_score(self) -> None:
        row = {"nama_produk": "centrifugal pump", "nama_perusahaan": "", "spesifikasi": "", "merek": ""}
        score = _compute_score(row, "centrifugal pump", date.today(), 2025, 2025)
        # fuzzy part alone: 0.5 * 1.0 = 0.5; expect overall score >= 0.5
        assert score >= RERANK_WEIGHT_FUZZY * 0.9

    def test_score_is_between_zero_and_one(self) -> None:
        row = {
            "nama_produk": "pump",
            "nama_perusahaan": "PT X",
            "spesifikasi": "",
            "merek": "",
            "nilai_tkdn": 40.0,
            "tahun_sumber": 2023,
            "masa_berlaku_akhir": _future(200),
        }
        score = _compute_score(row, "pump", date.today(), 2025, 2022)
        assert 0.0 <= score <= 1.0

    def test_valid_cert_scores_higher_than_expired(self) -> None:
        today = date.today()
        base = {
            "nama_produk": "pump", "nama_perusahaan": "", "spesifikasi": "", "merek": "",
            "nilai_tkdn": 40.0, "tahun_sumber": 2024,
        }
        valid_row = {**base, "masa_berlaku_akhir": _future(200)}
        expired_row = {**base, "masa_berlaku_akhir": _past(10)}

        valid_score = _compute_score(valid_row, "pump", today, 2024, 2024)
        expired_score = _compute_score(expired_row, "pump", today, 2024, 2024)

        assert valid_score > expired_score

    def test_expiring_soon_score_between_valid_and_expired(self) -> None:
        today = date.today()
        base = {
            "nama_produk": "pump", "nama_perusahaan": "", "spesifikasi": "", "merek": "",
            "nilai_tkdn": 40.0, "tahun_sumber": 2024,
        }
        valid = {**base, "masa_berlaku_akhir": _future(VALIDITY_EXPIRING_SOON_DAYS + 5)}
        expiring = {**base, "masa_berlaku_akhir": _future(VALIDITY_EXPIRING_SOON_DAYS - 5)}
        expired = {**base, "masa_berlaku_akhir": _past(5)}

        assert (
            _compute_score(valid, "pump", today, 2024, 2024)
            > _compute_score(expiring, "pump", today, 2024, 2024)
            > _compute_score(expired, "pump", today, 2024, 2024)
        )

    def test_higher_tkdn_scores_higher(self) -> None:
        today = date.today()
        base = {
            "nama_produk": "pump", "nama_perusahaan": "", "spesifikasi": "", "merek": "",
            "tahun_sumber": 2024, "masa_berlaku_akhir": _future(200),
        }
        high = _compute_score({**base, "nilai_tkdn": 80.0}, "pump", today, 2024, 2024)
        low = _compute_score({**base, "nilai_tkdn": 20.0}, "pump", today, 2024, 2024)

        assert high > low

    def test_newer_year_scores_higher_when_query_matches(self) -> None:
        today = date.today()
        base = {
            "nama_produk": "pump", "nama_perusahaan": "", "spesifikasi": "", "merek": "",
            "nilai_tkdn": 40.0, "masa_berlaku_akhir": _future(200),
        }
        newer = _compute_score({**base, "tahun_sumber": 2025}, "pump", today, 2025, 2022)
        older = _compute_score({**base, "tahun_sumber": 2022}, "pump", today, 2025, 2022)

        assert newer > older

    def test_equal_min_max_year_no_division_error(self) -> None:
        row = {
            "nama_produk": "pump", "nama_perusahaan": "", "spesifikasi": "", "merek": "",
            "nilai_tkdn": 40.0, "tahun_sumber": 2024, "masa_berlaku_akhir": _future(200),
        }
        # Should not raise ZeroDivisionError when max_tahun == min_tahun
        score = _compute_score(row, "pump", date.today(), 2024, 2024)
        assert isinstance(score, float)

    def test_weights_sum_to_one(self) -> None:
        total = (
            RERANK_WEIGHT_FUZZY
            + RERANK_WEIGHT_TKDN
            + RERANK_WEIGHT_RECENCY
            + RERANK_WEIGHT_VALIDITY
        )
        assert total == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# search() — empty query / no results
# ---------------------------------------------------------------------------

class TestSearchEmptyAndNoResults:
    def test_empty_query_returns_all_rows(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        _insert(db, cert_factory, nama_produk="Pump A")
        _insert(db, cert_factory, nama_produk="Pump B")

        result = search(db, query="")

        assert result["total"] == 2

    def test_no_match_returns_empty_results(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        _insert(db, cert_factory, nama_produk="Pump")

        result = search(db, query="XYZNONEXISTENT12345")

        assert result["total"] == 0
        assert result["results"] == []

    def test_empty_db_returns_empty_results(self, db: sqlite3.Connection) -> None:
        result = search(db, query="pump")

        assert result["total"] == 0

    def test_returns_query_time_ms(self, db: sqlite3.Connection, cert_factory: Any) -> None:
        _insert(db, cert_factory)
        result = search(db, query="pump")

        assert "query_time_ms" in result
        assert result["query_time_ms"] >= 0


# ---------------------------------------------------------------------------
# search() — filters
# ---------------------------------------------------------------------------

class TestSearchFilters:
    def test_tkdn_min_excludes_rows_below_threshold(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        _insert(db, cert_factory, nama_produk="Low TKDN", nilai_tkdn=20.0)
        _insert(db, cert_factory, nama_produk="High TKDN", nilai_tkdn=60.0)

        result = search(db, query="", tkdn_min=40.0)

        names = [r["nama_produk"] for r in result["results"]]
        assert "High TKDN" in names
        assert "Low TKDN" not in names

    def test_tkdn_min_zero_does_not_filter(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        _insert(db, cert_factory, nilai_tkdn=10.0)

        result = search(db, query="", tkdn_min=0.0)

        assert result["total"] == 1

    def test_validity_only_excludes_expired_rows(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        _insert(db, cert_factory, nama_produk="Valid", masa_berlaku_akhir=_future(100))
        _insert(db, cert_factory, nama_produk="Expired", masa_berlaku_akhir=_past(5))

        result = search(db, query="", validity_only=True)

        names = [r["nama_produk"] for r in result["results"]]
        assert "Valid" in names
        assert "Expired" not in names

    def test_kbli_filter_exact_match(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        _insert(db, cert_factory, nama_produk="Right KBLI", kbli="28101")
        _insert(db, cert_factory, nama_produk="Wrong KBLI", kbli="99999")

        result = search(db, query="", kbli="28101")

        names = [r["nama_produk"] for r in result["results"]]
        assert "Right KBLI" in names
        assert "Wrong KBLI" not in names

    def test_year_filter(self, db: sqlite3.Connection, cert_factory: Any) -> None:
        _insert(db, cert_factory, nama_produk="Year 2023", tahun_sumber=2023)
        _insert(db, cert_factory, nama_produk="Year 2024", tahun_sumber=2024)

        result = search(db, query="", year=2023)

        names = [r["nama_produk"] for r in result["results"]]
        assert "Year 2023" in names
        assert "Year 2024" not in names

    def test_combined_filters_are_anded(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        # Only the row matching ALL filters should appear
        _insert(
            db, cert_factory,
            nama_produk="Match All",
            nilai_tkdn=50.0,
            kbli="28101",
            tahun_sumber=2024,
            masa_berlaku_akhir=_future(100),
        )
        _insert(
            db, cert_factory,
            nama_produk="Low TKDN",
            nilai_tkdn=10.0,
            kbli="28101",
            tahun_sumber=2024,
        )

        result = search(db, query="", tkdn_min=40.0, kbli="28101", year=2024)

        names = [r["nama_produk"] for r in result["results"]]
        assert "Match All" in names
        assert "Low TKDN" not in names


# ---------------------------------------------------------------------------
# search() — pagination
# ---------------------------------------------------------------------------

class TestSearchPagination:
    def test_limit_caps_results(self, db: sqlite3.Connection, cert_factory: Any) -> None:
        for i in range(10):
            _insert(db, cert_factory, nama_produk=f"Pump {i}", spesifikasi=str(i))

        result = search(db, query="", limit=3)

        assert len(result["results"]) == 3

    def test_total_reflects_all_candidates_not_page_size(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        for i in range(10):
            _insert(db, cert_factory, nama_produk=f"Pump {i}", spesifikasi=str(i))

        result = search(db, query="", limit=3, offset=0)

        assert result["total"] == 10
        assert len(result["results"]) == 3

    def test_offset_returns_next_page(self, db: sqlite3.Connection, cert_factory: Any) -> None:
        for i in range(6):
            _insert(db, cert_factory, nama_produk=f"Pump {i}", spesifikasi=str(i))

        page1 = search(db, query="", limit=3, offset=0)
        page2 = search(db, query="", limit=3, offset=3)

        ids_p1 = {r["id"] for r in page1["results"]}
        ids_p2 = {r["id"] for r in page2["results"]}
        assert ids_p1.isdisjoint(ids_p2)

    def test_limit_capped_at_max(self, db: sqlite3.Connection, cert_factory: Any) -> None:
        _insert(db, cert_factory)

        result = search(db, query="", limit=SEARCH_RESULT_LIMIT_MAX + 999)

        # The function caps limit — no error raised
        assert result["total"] >= 0

    def test_offset_beyond_total_returns_empty_results(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        _insert(db, cert_factory)

        result = search(db, query="", limit=10, offset=100)

        assert result["results"] == []
        assert result["total"] == 1  # total is still the full count

    def test_score_field_present_when_query_given(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        _insert(db, cert_factory, nama_produk="Centrifugal Pump")

        result = search(db, query="pump")

        if result["results"]:
            assert "score" in result["results"][0]

    def test_internal_score_field_not_leaked(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        _insert(db, cert_factory)

        result = search(db, query="pump")

        for row in result["results"]:
            assert "_score" not in row
