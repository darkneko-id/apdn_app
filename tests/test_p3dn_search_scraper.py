"""Tests for p3dn_search_scraper.py — upsert_p3dn_rows logic and pagination."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

import pytest
from bs4 import BeautifulSoup

from tkdn_finder.merger import merge_and_upsert
from tkdn_finder.p3dn_search_scraper import upsert_p3dn_rows


def _find_next_page_link(html: str, page: int) -> str | None:
    """Mirror the pagination detection logic from scrape_p3dn_search."""
    soup = BeautifulSoup(html, "lxml")
    target_hal = f"hal={page + 1}"
    for a in soup.find_all("a", href=True):
        href = str(a.get("href", ""))
        idx = href.find(target_hal)
        if idx == -1:
            continue
        after = href[idx + len(target_hal):]
        if not after or not after[0].isdigit():
            return href
    return None


class TestPaginationDetection:
    def test_finds_numbered_link(self) -> None:
        html = '<a href="search.php?hal=2">2</a>'
        assert _find_next_page_link(html, 1) is not None

    def test_finds_next_arrow_link(self) -> None:
        """A 'Next »' button with hal=2 in href should be detected even without digit text."""
        html = '<a href="search.php?hal=2">Selanjutnya &raquo;</a>'
        assert _find_next_page_link(html, 1) is not None

    def test_does_not_match_hal_prefix(self) -> None:
        """hal=2 must not match when href contains hal=20 (only)."""
        html = '<a href="search.php?hal=20">20</a>'
        assert _find_next_page_link(html, 1) is None

    def test_returns_none_on_last_page(self) -> None:
        """No link for page+1 should return None, ending pagination."""
        html = '<a href="search.php?hal=3">3</a>'
        assert _find_next_page_link(html, 4) is None

    def test_finds_link_among_multiple_pagination_anchors(self) -> None:
        html = """
        <a href="search.php?hal=1">1</a>
        <a href="search.php?hal=2">2</a>
        <span>3</span>
        <a href="search.php?hal=4">4</a>
        """
        assert _find_next_page_link(html, 3) == "search.php?hal=4"


TODAY = date(2026, 6, 25)
TODAY_STR = "2026-06-25"


def _count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM tkdn_certificate").fetchone()[0]


def _fetch_one(conn: sqlite3.Connection, **where: Any) -> sqlite3.Row | None:
    col, val = next(iter(where.items()))
    return conn.execute(
        f"SELECT * FROM tkdn_certificate WHERE {col} = ?", (val,)
    ).fetchone()


def _fetch_all(conn: sqlite3.Connection, nama_produk: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM tkdn_certificate WHERE nama_produk = ?", (nama_produk,)
    ).fetchall()


class TestUpsertP3dnRowsUpdatesExisting:
    def test_sets_p3dn_search_last_seen_on_matching_row(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [cert_factory(nama_produk="Seamless Pipe", nilai_tkdn=10.29, tipe="")])

        stats = upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "Seamless Pipe", "spesifikasi": "6 inch 200 GPM", "nilai_tkdn": 10.29}],
            TODAY,
        )

        assert stats["updated"] >= 1
        assert stats["inserted"] == 0
        assert _count(db) == 1  # no duplicate created
        row = _fetch_one(db, nama_produk="Seamless Pipe")
        assert row is not None
        assert row["p3dn_search_last_seen"] == TODAY_STR

    def test_fuzzy_tkdn_tolerance_matches_within_half_percent(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [cert_factory(nama_produk="ERW Pipe", nilai_tkdn=58.30)])

        stats = upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "ERW Pipe", "spesifikasi": "6 inch 200 GPM", "nilai_tkdn": 58.35}],
            TODAY,
        )

        assert stats["updated"] >= 1
        assert _count(db) == 1

    def test_updates_all_tipe_variants_for_product(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [cert_factory(tipe="Variant A", nilai_tkdn=40.0)])
        merge_and_upsert(db, [cert_factory(tipe="Variant B", nilai_tkdn=40.0)])
        assert _count(db) == 2

        stats = upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "Centrifugal Pump", "spesifikasi": "6 inch 200 GPM", "nilai_tkdn": 40.0}],
            TODAY,
        )

        assert stats["updated"] == 2
        rows = _fetch_all(db, "Centrifugal Pump")
        assert all(r["p3dn_search_last_seen"] == TODAY_STR for r in rows)


class TestUpsertP3dnRowsInsertsNew:
    def test_inserts_product_absent_from_db(self, db: sqlite3.Connection) -> None:
        stats = upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "Pipa Baja ERW", "spesifikasi": "", "nilai_tkdn": 58.30}],
            TODAY,
        )

        assert stats["inserted"] == 1
        assert _count(db) == 1
        row = _fetch_one(db, nama_produk="Pipa Baja ERW")
        assert row is not None
        assert row["p3dn_search_last_seen"] == TODAY_STR
        assert row["masa_berlaku_akhir"] is None
        assert row["tahun_sumber"] is None

    def test_inserts_alamat_when_provided(self, db: sqlite3.Connection) -> None:
        upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "Pipa SAW", "spesifikasi": "", "nilai_tkdn": 53.85,
              "alamat": "Jl. Baja No. 1"}],
            TODAY,
        )

        row = _fetch_one(db, nama_produk="Pipa SAW")
        assert row is not None
        assert row["alamat"] == "Jl. Baja No. 1"

    def test_skips_row_with_empty_produk(self, db: sqlite3.Connection) -> None:
        stats = upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "", "spesifikasi": "", "nilai_tkdn": 40.0}],
            TODAY,
        )

        assert stats["skipped"] == 1
        assert _count(db) == 0


class TestUpsertP3dnRowsIdempotent:
    def test_no_duplicate_on_second_call(self, db: sqlite3.Connection) -> None:
        rows = [{"nama_produk": "Pipa ERW", "spesifikasi": "", "nilai_tkdn": 58.30}]
        upsert_p3dn_rows(db, "PT Test Corp", rows, TODAY)
        upsert_p3dn_rows(db, "PT Test Corp", rows, TODAY)

        assert _count(db) == 1

    def test_last_seen_updated_on_second_call(self, db: sqlite3.Connection) -> None:
        rows = [{"nama_produk": "Pipa ERW", "spesifikasi": "", "nilai_tkdn": 58.30}]
        upsert_p3dn_rows(db, "PT Test Corp", rows, date(2026, 6, 24))
        upsert_p3dn_rows(db, "PT Test Corp", rows, TODAY)

        row = _fetch_one(db, nama_produk="Pipa ERW")
        assert row is not None
        assert row["p3dn_search_last_seen"] == TODAY_STR


class TestUpsertP3dnRowsNotFoundMarking:
    def test_absent_record_marked_p3dn_not_found_since(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """Record in DB but not in P3DN scrape should get p3dn_not_found_since set."""
        merge_and_upsert(db, [cert_factory(nama_produk="Gate Valve", nilai_tkdn=30.0, tipe="")])

        # Scrape returns a DIFFERENT product for the same company
        upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "Check Valve", "spesifikasi": "", "nilai_tkdn": 35.0}],
            TODAY,
        )

        gate_valve = _fetch_one(db, nama_produk="Gate Valve")
        assert gate_valve is not None
        assert gate_valve["p3dn_not_found_since"] == TODAY_STR

        check_valve = _fetch_one(db, nama_produk="Check Valve")
        assert check_valve is not None
        assert check_valve["p3dn_not_found_since"] is None

    def test_found_record_clears_p3dn_not_found_since(
        self, db: sqlite3.Connection
    ) -> None:
        """A record marked as absent should be cleared when found again."""
        # First scrape: Pipa A found, Pipa B not found
        upsert_p3dn_rows(
            db, "PT Test Corp",
            [
                {"nama_produk": "Pipa A", "spesifikasi": "", "nilai_tkdn": 40.0},
                {"nama_produk": "Pipa B", "spesifikasi": "", "nilai_tkdn": 50.0},
            ],
            date(2026, 6, 24),
        )
        upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "Pipa A", "spesifikasi": "", "nilai_tkdn": 40.0}],
            date(2026, 6, 25),
        )
        pipa_b = _fetch_one(db, nama_produk="Pipa B")
        assert pipa_b is not None
        assert pipa_b["p3dn_not_found_since"] == "2026-06-25"

        # Second scrape: both found — Pipa B's not_found_since should be cleared
        upsert_p3dn_rows(
            db, "PT Test Corp",
            [
                {"nama_produk": "Pipa A", "spesifikasi": "", "nilai_tkdn": 40.0},
                {"nama_produk": "Pipa B", "spesifikasi": "", "nilai_tkdn": 50.0},
            ],
            TODAY,
        )
        pipa_b_after = _fetch_one(db, nama_produk="Pipa B")
        assert pipa_b_after is not None
        assert pipa_b_after["p3dn_not_found_since"] is None
        assert pipa_b_after["p3dn_search_last_seen"] == TODAY_STR

    def test_absent_record_not_marked_when_scrape_returns_empty(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """Empty scrape result should not mark any records as absent."""
        merge_and_upsert(db, [cert_factory(nama_produk="Gate Valve", nilai_tkdn=30.0, tipe="")])

        # upsert_p3dn_rows with empty list (would only be called if scrape succeeded)
        upsert_p3dn_rows(db, "PT Test Corp", [], TODAY)

        gate_valve = _fetch_one(db, nama_produk="Gate Valve")
        assert gate_valve is not None
        assert gate_valve["p3dn_not_found_since"] is None

    def test_other_company_records_not_affected(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """p3dn_not_found_since marking must not cross company boundaries."""
        merge_and_upsert(db, [cert_factory(
            nama_perusahaan="PT Other Corp", nama_produk="Valve", nilai_tkdn=25.0, tipe=""
        )])

        upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "Pump", "spesifikasi": "", "nilai_tkdn": 40.0}],
            TODAY,
        )

        other_valve = _fetch_one(db, nama_produk="Valve")
        assert other_valve is not None
        assert other_valve["p3dn_not_found_since"] is None
