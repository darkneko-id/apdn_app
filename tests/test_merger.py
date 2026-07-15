"""Tests for merger.py — upsert semantics and deduplication logic."""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from tkdn_finder.merger import merge_and_upsert


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM tkdn_certificate").fetchone()[0]


def _fetch_one(conn: sqlite3.Connection, **where: Any) -> sqlite3.Row | None:
    col, val = next(iter(where.items()))
    return conn.execute(
        f"SELECT * FROM tkdn_certificate WHERE {col} = ?", (val,)
    ).fetchone()


# ---------------------------------------------------------------------------
# Basic insert / update counting
# ---------------------------------------------------------------------------

class TestMergeAndUpsertCounts:
    def test_new_row_increments_inserted(self, db: sqlite3.Connection, cert_factory: Any) -> None:
        stats = merge_and_upsert(db, [cert_factory()])

        assert stats["inserted"] == 1
        assert stats["updated"] == 0
        assert stats["skipped"] == 0

    def test_same_row_twice_increments_updated(self, db: sqlite3.Connection, cert_factory: Any) -> None:
        row = cert_factory()
        merge_and_upsert(db, [row])
        stats = merge_and_upsert(db, [row])

        assert stats["inserted"] == 0
        assert stats["updated"] == 1
        assert _count(db) == 1  # no duplicate created

    def test_two_distinct_rows_both_inserted(self, db: sqlite3.Connection, cert_factory: Any) -> None:
        stats = merge_and_upsert(db, [
            cert_factory(nama_produk="Pump A"),
            cert_factory(nama_produk="Pump B"),
        ])

        assert stats["inserted"] == 2
        assert _count(db) == 2

    def test_integrity_error_increments_skipped(self, db: sqlite3.Connection) -> None:
        # Force a row that violates NOT NULL constraint on nama_produk
        bad_row = {
            "nama_perusahaan": None,  # NOT NULL violation
            "nama_produk": None,
            "spesifikasi": "",
            "merek": "",
            "tipe": "",
            "nilai_tkdn": None,
            "kode_hs": None,
            "kbli": None,
            "kelompok_barang": None,
            "alamat": None,
            "provinsi": None,
            "masa_berlaku_akhir": None,
            "tahun_sumber": None,
        }
        stats = merge_and_upsert(db, [bad_row])

        assert stats["skipped"] == 1
        assert _count(db) == 0


# ---------------------------------------------------------------------------
# Dedup key: (nama_perusahaan, nama_produk, spesifikasi, merek, nilai_tkdn, tipe)
# ---------------------------------------------------------------------------

class TestDedupKey:
    def test_different_tipe_creates_separate_rows(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [
            cert_factory(tipe="Type A"),
            cert_factory(tipe="Type B"),
        ])

        assert _count(db) == 2

    def test_different_merek_creates_separate_rows(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [
            cert_factory(merek="BrandA"),
            cert_factory(merek="BrandB"),
        ])

        assert _count(db) == 2

    def test_different_nilai_tkdn_creates_separate_rows(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [
            cert_factory(nilai_tkdn=40.0),
            cert_factory(nilai_tkdn=50.0),
        ])

        assert _count(db) == 2

    def test_same_key_different_spesifikasi_creates_separate_rows(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [
            cert_factory(spesifikasi="6 inch"),
            cert_factory(spesifikasi="8 inch"),
        ])

        assert _count(db) == 2


# ---------------------------------------------------------------------------
# Tipe preservation (key business rule)
# ---------------------------------------------------------------------------

class TestTipePreservation:
    def test_enriched_tipe_preserved_when_reimported_with_empty_tipe(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """Core invariant: P3DN re-download (tipe='') must not overwrite enriched tipe."""
        # 1. First import: tipe empty (as P3DN always sends it)
        merge_and_upsert(db, [cert_factory(tipe="")])

        # 2. Simulate tipe enrichment: manually set tipe to a real value
        db.execute(
            "UPDATE tkdn_certificate SET tipe = 'Cable Ladder SLHD' WHERE nama_produk = ?",
            ("Centrifugal Pump",),
        )
        db.commit()

        # 3. Re-download: merge same row with tipe='' again
        # Merger pre-check: enriched variant exists → update metadata in-place, no new row
        merge_and_upsert(db, [cert_factory(tipe="")])

        assert _count(db) == 1  # no redundant tipe='' row inserted
        row = _fetch_one(db, nama_produk="Centrifugal Pump")
        assert row is not None
        assert row["tipe"] == "Cable Ladder SLHD"  # enriched tipe preserved

    def test_multiple_enriched_tipe_variants_preserved_on_reimport(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """Re-download with tipe='' must not clobber multiple enriched tipe variants."""
        merge_and_upsert(db, [cert_factory(tipe="Type A")])
        merge_and_upsert(db, [cert_factory(tipe="Type B")])
        assert _count(db) == 2

        merge_and_upsert(db, [cert_factory(tipe="")])

        assert _count(db) == 2  # no tipe='' row added alongside enriched variants

    def test_backfilled_merek_preserved_when_reimported_with_empty_merek(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """Regression: Update Tipe backfills merek (and tipe) from search.php
        onto a bulk row whose excel Merk was empty. The next scheduled
        re-download of that excel row (merek='') must update the enriched row
        in place — not re-insert the redundant tipe=''/merek='' skeleton."""
        merge_and_upsert(db, [cert_factory(tipe="", merek="")])

        # Simulate P3DN search enrichment backfilling both fields
        db.execute(
            "UPDATE tkdn_certificate SET tipe = 'SAW', merek = 'BKS' "
            "WHERE nama_produk = ?",
            ("Centrifugal Pump",),
        )
        db.commit()

        merge_and_upsert(db, [cert_factory(tipe="", merek="")])

        assert _count(db) == 1
        row = _fetch_one(db, nama_produk="Centrifugal Pump")
        assert row is not None
        assert row["tipe"] == "SAW"
        assert row["merek"] == "BKS"

    def test_backfilled_merek_only_preserved_on_reimport(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """Same as above but only merek was backfilled (tipe still '')."""
        merge_and_upsert(db, [cert_factory(tipe="", merek="")])
        db.execute(
            "UPDATE tkdn_certificate SET merek = 'BKS' WHERE nama_produk = ?",
            ("Centrifugal Pump",),
        )
        db.commit()

        merge_and_upsert(db, [cert_factory(tipe="", merek="")])

        assert _count(db) == 1
        row = _fetch_one(db, nama_produk="Centrifugal Pump")
        assert row is not None
        assert row["merek"] == "BKS"

    def test_distinct_excel_merek_still_creates_separate_row(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """A NON-empty excel merek that differs from the stored one is a
        distinct certificate — the relaxed pre-check must not swallow it."""
        merge_and_upsert(db, [cert_factory(tipe="", merek="BrandX")])
        merge_and_upsert(db, [cert_factory(tipe="", merek="BrandY")])

        assert _count(db) == 2

    def test_nonempty_tipe_from_source_creates_distinct_row(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        # tipe='' and tipe='Type A' are distinct rows under the new UNIQUE key
        merge_and_upsert(db, [cert_factory(tipe="")])
        merge_and_upsert(db, [cert_factory(tipe="Type A")])

        assert _count(db) == 2
        rows = db.execute(
            "SELECT tipe FROM tkdn_certificate ORDER BY tipe"
        ).fetchall()
        assert {r["tipe"] for r in rows} == {"", "Type A"}


# ---------------------------------------------------------------------------
# Null coercion — spesifikasi / tipe / merek must never be NULL in the key
# ---------------------------------------------------------------------------

class TestNullCoercion:
    def test_none_tipe_coerced_to_empty_string(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [cert_factory(tipe=None)])

        row = _fetch_one(db, nama_produk="Centrifugal Pump")
        assert row is not None
        assert row["tipe"] == ""

    def test_none_spesifikasi_coerced_to_empty_string(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [cert_factory(spesifikasi=None)])

        row = _fetch_one(db, nama_produk="Centrifugal Pump")
        assert row is not None
        assert row["spesifikasi"] == ""

    def test_none_merek_coerced_to_empty_string(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [cert_factory(merek=None)])

        row = _fetch_one(db, nama_produk="Centrifugal Pump")
        assert row is not None
        assert row["merek"] == ""

    def test_coerced_row_deduplicates_correctly_on_reimport(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        # None and "" should be treated the same for the dedup key
        merge_and_upsert(db, [cert_factory(spesifikasi=None)])
        merge_and_upsert(db, [cert_factory(spesifikasi="")])

        assert _count(db) == 1  # treated as same row, not duplicate


# ---------------------------------------------------------------------------
# Transaction integrity
# ---------------------------------------------------------------------------

class TestTransaction:
    def test_all_rows_committed_in_one_batch(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        rows = [cert_factory(nama_produk=f"Pump {i}") for i in range(5)]
        merge_and_upsert(db, rows)

        assert _count(db) == 5

    def test_ingested_at_set_on_insert(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [cert_factory()])

        row = _fetch_one(db, nama_produk="Centrifugal Pump")
        assert row is not None
        assert row["ingested_at"] is not None
