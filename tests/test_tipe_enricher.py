"""Tests for tipe_enricher.enrich_tipe_in_db — normalized matching and upserts."""

from __future__ import annotations

import sqlite3
from typing import Any

from tkdn_finder.merger import merge_and_upsert
from tkdn_finder.tipe_enricher import enrich_tipe_in_db


def _count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM tkdn_certificate").fetchone()[0]


def _rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM tkdn_certificate ORDER BY id").fetchall()


def _scraped(**kwargs: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "nama_perusahaan": "PT Test Corp",
        "kelompok_barang": "Pompa",
        "nama_produk": "Centrifugal Pump",
        "spesifikasi": "6 inch 200 GPM",
        "tipe": "CP-100",
        "merek": "BrandX",
        "nilai_tkdn_str": "40.00",
    }
    row.update(kwargs)
    return row


class TestEnrichUpdatesEmptyTipe:
    def test_backfills_tipe_on_exact_match(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [cert_factory(tipe="")])

        stats = enrich_tipe_in_db(db, "PT Test Corp", [_scraped()])

        assert stats["updated"] == 1
        assert _count(db) == 1
        assert _rows(db)[0]["tipe"] == "CP-100"

    def test_matches_despite_whitespace_and_dash_differences(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """Regression: tkdn.kemenperin.go.id renders the same certificate text
        with different spacing/dashes than the bulk export. The old exact-string
        matching missed the row and cloned a new line item instead."""
        merge_and_upsert(db, [cert_factory(
            nama_produk="Heat Treatment Process - Carbon Steel Seamless Casing",
            spesifikasi=("API 5CT, Grade N80/N80Q, L80, C90, R95, T95, P110, "
                         "Q125, Dia. 4 1/2 – 13 3/8 inch, R1, R2, R3, PE"),
            nilai_tkdn=35.53,
            tipe="",
        )])

        stats = enrich_tipe_in_db(db, "PT Test Corp", [_scraped(
            nama_produk="Heat  Treatment Process – Carbon Steel Seamless Casing",
            spesifikasi=("API 5CT, Grade N80/N80Q, L80, C90, R95, T95, P110, "
                         "Q125, Dia. 4 1/2 - 13 3/8 inch, R1,R2, R3, PE"),
            tipe="HT-CS",
            nilai_tkdn_str="35,53",  # comma decimal must parse too
        )])

        assert stats["updated"] == 1
        assert stats["inserted"] == 0
        assert _count(db) == 1
        assert _rows(db)[0]["tipe"] == "HT-CS"

    def test_fuzzy_fallback_backfills_tipe_despite_reworded_spec(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """'Dia.' vs 'Diameter' rewording must not stop the tipe backfill."""
        merge_and_upsert(db, [cert_factory(
            nama_produk="Carbon Steel Seamless Casing",
            spesifikasi="API 5CT, Grade N80/N80Q, Dia. 4 1/2 – 13 3/8 inch, R1, R2, R3, PE",
            nilai_tkdn=51.47,
            tipe="",
        )])

        stats = enrich_tipe_in_db(db, "PT Test Corp", [_scraped(
            nama_produk="Carbon Steel Seamless Casing",
            spesifikasi="API 5CT, Grade N80/N80Q, Diameter 4 1/2 - 13 3/8 inch, R1, R2, R3, PE",
            tipe="Casing Plain End",
            nilai_tkdn_str="51.47",
        )])

        assert stats["updated"] == 1
        assert stats["inserted"] == 0
        assert _count(db) == 1
        assert _rows(db)[0]["tipe"] == "Casing Plain End"

    def test_keeps_bulk_export_spelling_when_cloning_variants(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """Cloned tipe-variant rows must reuse the stored text, not the scraped
        variant spelling — otherwise the bulk re-import won't dedup them."""
        merge_and_upsert(db, [cert_factory(tipe="")])

        stats = enrich_tipe_in_db(db, "PT Test Corp", [
            _scraped(nama_produk="CENTRIFUGAL  PUMP", tipe="CP-100"),
            _scraped(nama_produk="CENTRIFUGAL  PUMP", tipe="CP-200"),
        ])

        assert stats["updated"] == 1
        assert stats["inserted"] == 1
        rows = _rows(db)
        assert {r["tipe"] for r in rows} == {"CP-100", "CP-200"}
        assert all(r["nama_produk"] == "Centrifugal Pump" for r in rows)
        # Clone inherits bulk-export metadata
        assert all(r["masa_berlaku_akhir"] == "2027-12-31" for r in rows)

    def test_removes_stale_empty_tipe_row_when_variant_already_exists(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [cert_factory(tipe="")])
        merge_and_upsert(db, [cert_factory(tipe="CP-100")])
        assert _count(db) == 2

        stats = enrich_tipe_in_db(db, "PT Test Corp", [_scraped(tipe="CP-100")])

        assert stats["skipped"] == 1
        assert _count(db) == 1
        assert _rows(db)[0]["tipe"] == "CP-100"

    def test_idempotent_on_second_run(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [cert_factory(tipe="")])
        scraped = [_scraped(tipe="CP-100"), _scraped(tipe="CP-200")]

        enrich_tipe_in_db(db, "PT Test Corp", scraped)
        stats = enrich_tipe_in_db(db, "PT Test Corp", scraped)

        assert stats["inserted"] == 0
        assert stats["updated"] == 0
        assert _count(db) == 2

    def test_recovers_from_corrupted_skeleton_that_stole_the_tipe(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        """Regression (PT Artas Energi Petrogas, post-fix relapse): a P3DN-only
        skeleton row (tahun_sumber IS NULL) can have gotten its tipe wrongly
        set by an earlier buggy enrichment run. The true bulk-export row
        (tipe='', has provenance) must win: get the tipe, and the skeleton
        must be deleted — not the other way around."""
        merge_and_upsert(db, [cert_factory(
            nama_produk="Carbon Steel Seamless Casing",
            spesifikasi="API 5CT, Grade N80/N80Q, L80, C90, R95, T95, P110, Q125",
            nilai_tkdn=51.47,
            tipe="",
        )])
        # Corrupted skeleton: no tahun_sumber/masa_berlaku (P3DN-only import),
        # but tipe was already (wrongly) set by a stale enrichment match.
        db.execute(
            """INSERT INTO tkdn_certificate
               (nama_perusahaan, nama_produk, spesifikasi, merek, tipe, nilai_tkdn,
                tahun_sumber, masa_berlaku_akhir, p3dn_search_last_seen)
               VALUES ('PT Test Corp', 'Carbon Steel Seamless Casing',
                       'API 5CT, Grade N80/N80Q, L80, C90, R95, T95, P110, Q125',
                       '', 'Casing Plain End', 51.47, NULL, NULL, '2026-07-15')"""
        )
        db.commit()
        assert _count(db) == 2

        stats = enrich_tipe_in_db(db, "PT Test Corp", [_scraped(
            nama_produk="Carbon Steel Seamless Casing",
            spesifikasi="API 5CT, Grade N80/N80Q, L80, C90, R95, T95, P110, Q125",
            tipe="Casing Plain End",
            nilai_tkdn_str="51.47",
        )])

        assert stats["deduped"] == 1
        assert _count(db) == 1
        row = _rows(db)[0]
        assert row["tipe"] == "Casing Plain End"
        assert row["masa_berlaku_akhir"] == "2027-12-31"  # bulk-export row survived

    def test_row_without_tipe_is_ignored(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [cert_factory(tipe="")])

        stats = enrich_tipe_in_db(db, "PT Test Corp", [_scraped(tipe="")])

        assert stats == {"updated": 0, "inserted": 0, "skipped": 0, "deduped": 0}
        assert _rows(db)[0]["tipe"] == ""
