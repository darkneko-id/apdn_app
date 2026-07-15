"""Tests for p3dn_search_scraper.py — upsert_p3dn_rows logic and pagination."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

import httpx
import pytest
from bs4 import BeautifulSoup

from tkdn_finder.merger import merge_and_upsert
from tkdn_finder.p3dn_search_scraper import scrape_p3dn_search, upsert_p3dn_rows


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


class _FakeResponse:
    def __init__(self, html: str) -> None:
        self.text = html

    def raise_for_status(self) -> None:
        pass


class TestScrapePaginationPreservesSearchParams:
    async def test_page_2_request_carries_original_where_what(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Page 2+ must re-send where/what — following a bare href like
        'search.php?hal=2' would silently drop the company filter."""
        page1_html = """
        <table>
          <tr><th>Perusahaan</th><th>Produk</th><th>Spesifikasi</th><th>Nilai TKDN</th></tr>
          <tr><td>PT X</td><td>Produk A</td><td>Spec A</td><td>10.00</td></tr>
        </table>
        <a href="search.php?hal=2">Selanjutnya &raquo;</a>
        """
        page2_html = """
        <table>
          <tr><th>Perusahaan</th><th>Produk</th><th>Spesifikasi</th><th>Nilai TKDN</th></tr>
          <tr><td>PT X</td><td>Produk B</td><td>Spec B</td><td>20.00</td></tr>
        </table>
        """
        responses = [page1_html, page2_html]
        calls: list[dict[str, str] | None] = []

        async def fake_get(
            self: httpx.AsyncClient, url: str, params: dict[str, str] | None = None, **kwargs: Any
        ) -> _FakeResponse:
            calls.append(params)
            return _FakeResponse(responses.pop(0))

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

        rows = await scrape_p3dn_search("PT X", delay_seconds=0)

        assert len(calls) == 2
        assert calls[0] == {"where": "perush", "what": "PT X"}
        assert calls[1] == {"where": "perush", "what": "PT X", "hal": "2"}
        assert len(rows) == 2


class TestColumnFallbackNoCollision:
    async def test_no_spec_column_does_not_map_spesifikasi_to_tkdn_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Layout with no distinct spec column (0=No,1=Perusahaan,2=Produk,3=TKDN):
        the fallback must not read spesifikasi from the TKDN column itself."""
        html = """
        <table>
          <tr><th>No</th><th>Nama PT</th><th>Barang</th><th>Persentase</th></tr>
          <tr><td>1</td><td>PT X</td><td>Produk A</td><td>58.30</td></tr>
        </table>
        """

        async def fake_get(
            self: httpx.AsyncClient, url: str, params: dict[str, str] | None = None, **kwargs: Any
        ) -> _FakeResponse:
            return _FakeResponse(html)

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

        rows = await scrape_p3dn_search("PT X", delay_seconds=0)

        assert len(rows) == 1
        assert rows[0]["nama_produk"] == "Produk A"
        assert rows[0]["nilai_tkdn"] == 58.30
        assert rows[0]["spesifikasi"] == ""

    async def test_data_row_with_produk_like_text_not_mistaken_for_header(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A single accidental alias match (product name containing 'produk')
        must not cause _detect_columns to treat a data row as the header and
        skip every real data row after it."""
        html = """
        <table>
          <tr><th>No</th><th>Nama PT</th><th>Barang</th><th>Persentase</th></tr>
          <tr><td>1</td><td>PT X</td><td>Produk Andalan</td><td>58.30</td></tr>
          <tr><td>2</td><td>PT X</td><td>Produk Lainnya</td><td>40.00</td></tr>
        </table>
        """

        async def fake_get(
            self: httpx.AsyncClient, url: str, params: dict[str, str] | None = None, **kwargs: Any
        ) -> _FakeResponse:
            return _FakeResponse(html)

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

        rows = await scrape_p3dn_search("PT X", delay_seconds=0)

        assert len(rows) == 2
        assert {r["nama_produk"] for r in rows} == {"Produk Andalan", "Produk Lainnya"}


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

    def test_first_absence_date_is_preserved_across_repeated_scrapes(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """p3dn_not_found_since must pin the FIRST confirmed-absent date, not
        reset forward every time the record is still missing."""
        merge_and_upsert(db, [cert_factory(nama_produk="Gate Valve", nilai_tkdn=30.0, tipe="")])

        upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "Check Valve", "spesifikasi": "", "nilai_tkdn": 35.0}],
            date(2026, 6, 25),
        )
        first = _fetch_one(db, nama_produk="Gate Valve")
        assert first is not None
        assert first["p3dn_not_found_since"] == "2026-06-25"

        # Still absent a week later — the original date must not be overwritten
        upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "Check Valve", "spesifikasi": "", "nilai_tkdn": 35.0}],
            date(2026, 7, 2),
        )
        second = _fetch_one(db, nama_produk="Gate Valve")
        assert second is not None
        assert second["p3dn_not_found_since"] == "2026-06-25"


class TestUpsertP3dnRowsNormalizedMatching:
    def test_matches_despite_whitespace_and_case_differences(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """Scraped text often differs in case/whitespace from the bulk-export
        text for the same certificate; matching must not create a duplicate."""
        merge_and_upsert(db, [cert_factory(
            nama_produk="Seamless Pipe",
            spesifikasi="6 inch 200 GPM",
            nilai_tkdn=10.29,
            tipe="",
        )])

        stats = upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "seamless pipe", "spesifikasi": " 6 INCH 200 gpm ", "nilai_tkdn": 10.29}],
            TODAY,
        )

        assert stats["inserted"] == 0
        assert _count(db) == 1

    def test_matches_despite_internal_whitespace_and_dash_variants(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """Regression (PT Artas Energi Petrogas): the bulk export uses an
        en dash and single spaces; search.php renders the same spec with a
        plain hyphen and doubled/missing internal spaces. The old TRIM-only
        comparison missed the row, inserted a duplicate marked P3DN-aktif and
        flagged the original as 'Tidak ditemukan di P3DN'."""
        spec_db = ("API 5CT, Grade N80/N80Q, L80, C90, R95, T95, P110, Q125, "
                   "Dia. 4 1/2 – 13 3/8 inch, R1, R2, R3, PE")
        spec_scraped = ("API 5CT, Grade N80/N80Q, L80,  C90, R95, T95, P110, Q125, "
                        "Dia. 4 1/2 - 13 3/8 inch, R1, R2,R3, PE")
        merge_and_upsert(db, [cert_factory(
            nama_produk="Heat Treatment Process - Carbon Steel Seamless Casing",
            spesifikasi=spec_db,
            nilai_tkdn=35.53,
            tipe="",
        )])

        stats = upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "Heat Treatment Process – Carbon Steel Seamless Casing",
              "spesifikasi": spec_scraped, "nilai_tkdn": 35.53}],
            TODAY,
        )

        assert stats["inserted"] == 0
        assert stats["updated"] == 1
        assert _count(db) == 1
        row = _fetch_one(db, spesifikasi=spec_db)
        assert row is not None
        assert row["p3dn_search_last_seen"] == TODAY_STR
        assert row["p3dn_not_found_since"] is None

    def test_heals_skeleton_duplicate_created_by_old_matching(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """DBs corrupted by the old bug hold both the bulk-export row (flagged
        not-found) and a skeleton duplicate inserted from search.php. A re-scrape
        must delete the skeleton and rehabilitate the original row."""
        merge_and_upsert(db, [cert_factory(
            nama_produk="Casing Pipe", spesifikasi="API 5CT – Grade L80",
            nilai_tkdn=35.53, tipe="",
        )])
        db.execute(
            "UPDATE tkdn_certificate SET p3dn_not_found_since = '2026-06-01'"
        )
        # Skeleton duplicate as the old code inserted it (spec text differs slightly)
        db.execute(
            """INSERT INTO tkdn_certificate
               (nama_perusahaan, nama_produk, spesifikasi, merek, tipe, nilai_tkdn,
                p3dn_search_last_seen)
               VALUES ('PT Test Corp', 'Casing Pipe', 'API 5CT - Grade  L80', '', '',
                       35.53, '2026-06-01')"""
        )
        db.commit()
        assert _count(db) == 2

        stats = upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "Casing Pipe", "spesifikasi": "API 5CT - Grade L80",
              "nilai_tkdn": 35.53}],
            TODAY,
        )

        assert stats["deduped"] == 1
        assert stats["inserted"] == 0
        assert _count(db) == 1
        row = _fetch_one(db, nama_produk="Casing Pipe")
        assert row is not None
        assert row["masa_berlaku_akhir"] is not None  # the bulk-export row survived
        assert row["p3dn_search_last_seen"] == TODAY_STR
        assert row["p3dn_not_found_since"] is None

    def test_heals_skeleton_duplicate_whose_tipe_was_corrupted(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """Regression: a skeleton row (no bulk provenance) that had its tipe
        wrongly set by a stale enrichment match must still be recognized as
        the duplicate to remove — tipe being non-empty must not make it look
        like the authoritative row. Its tipe is merged onto the survivor."""
        merge_and_upsert(db, [cert_factory(
            nama_produk="Casing Pipe", spesifikasi="API 5CT – Grade L80",
            nilai_tkdn=51.47, tipe="",
        )])
        db.execute(
            """INSERT INTO tkdn_certificate
               (nama_perusahaan, nama_produk, spesifikasi, merek, tipe, nilai_tkdn,
                tahun_sumber, masa_berlaku_akhir, p3dn_search_last_seen)
               VALUES ('PT Test Corp', 'Casing Pipe', 'API 5CT - Grade L80', '',
                       'Casing Plain End', 51.47, NULL, NULL, '2026-06-01')"""
        )
        db.commit()
        assert _count(db) == 2

        stats = upsert_p3dn_rows(
            db, "PT Test Corp",
            [{"nama_produk": "Casing Pipe", "spesifikasi": "API 5CT - Grade L80",
              "nilai_tkdn": 51.47}],
            TODAY,
        )

        assert stats["deduped"] == 1
        assert _count(db) == 1
        row = _fetch_one(db, nama_produk="Casing Pipe")
        assert row is not None
        assert row["tipe"] == "Casing Plain End"  # recovered, not lost
        assert row["masa_berlaku_akhir"] is not None  # bulk-export row survived
        assert row["p3dn_search_last_seen"] == TODAY_STR

    def test_distinct_tkdn_values_still_insert_separate_rows(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """Normalized matching must not over-collapse: same product name with
        clearly different TKDN values are distinct certificates."""
        merge_and_upsert(db, [cert_factory(
            nama_produk="Steel Pipe", spesifikasi="", nilai_tkdn=25.0, tipe="",
        )])

        stats = upsert_p3dn_rows(
            db, "PT Test Corp",
            [
                {"nama_produk": "Steel Pipe", "spesifikasi": "", "nilai_tkdn": 25.0},
                {"nama_produk": "Steel Pipe", "spesifikasi": "", "nilai_tkdn": 31.7},
                {"nama_produk": "Steel Pipe", "spesifikasi": "", "nilai_tkdn": 42.9},
            ],
            TODAY,
        )

        assert stats["updated"] == 1
        assert stats["inserted"] == 2
        assert _count(db) == 3
