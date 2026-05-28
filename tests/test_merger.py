# tests/test_merger.py
"""Tests for the merger/upsert module."""

from __future__ import annotations

import sqlite3

import pytest

from tkdn_finder.merger import merge_and_upsert


SAMPLE_ROW = {
    "nama_perusahaan": "PT Contoh Indonesia",
    "nama_produk": "Pompa Sentrifugal",
    "spesifikasi": "Head 50m, Q 100 m3/h, 15 kW",
    "merek": "ContohPump",
    "tipe": "CS-100",
    "nilai_tkdn": 42.5,
    "kode_hs": "84137090",
    "kbli": "28131",
    "kelompok_barang": "Pompa dan Kompresor",
    "alamat": "Jl. Industri No 1, Jakarta",
    "provinsi": "DKI Jakarta",
    "masa_berlaku_akhir": "2027-12-31",
    "tahun_sumber": 2026,
}


def test_merge_inserts_new_row(db_conn: sqlite3.Connection) -> None:
    stats = merge_and_upsert(db_conn, [SAMPLE_ROW])
    assert stats["inserted"] >= 1

    row = db_conn.execute("SELECT * FROM tkdn_certificate").fetchone()
    assert row is not None
    assert row["nama_perusahaan"] == "PT Contoh Indonesia"
    assert row["nilai_tkdn"] == pytest.approx(42.5)


def test_merge_updates_on_duplicate_natural_key(db_conn: sqlite3.Connection) -> None:
    merge_and_upsert(db_conn, [SAMPLE_ROW])

    updated = {**SAMPLE_ROW, "nilai_tkdn": 55.0, "merek": "NewBrand"}
    merge_and_upsert(db_conn, [updated])

    rows = db_conn.execute("SELECT * FROM tkdn_certificate").fetchall()
    assert len(rows) == 1
    assert rows[0]["nilai_tkdn"] == pytest.approx(55.0)
    assert rows[0]["merek"] == "NewBrand"


def test_merge_multiple_rows(db_conn: sqlite3.Connection) -> None:
    rows = []
    for i in range(5):
        rows.append({
            **SAMPLE_ROW,
            "nama_produk": f"Produk {i}",
            "spesifikasi": f"Spesifikasi {i}",
        })

    stats = merge_and_upsert(db_conn, rows)
    count = db_conn.execute("SELECT COUNT(*) FROM tkdn_certificate").fetchone()[0]
    assert count == 5


def test_merge_empty_list(db_conn: sqlite3.Connection) -> None:
    stats = merge_and_upsert(db_conn, [])
    assert stats["inserted"] == 0
    assert stats["skipped"] == 0


def test_merge_handles_none_optional_fields(db_conn: sqlite3.Connection) -> None:
    row = {
        "nama_perusahaan": "PT Minimal",
        "nama_produk": "Produk Minimal",
        "spesifikasi": "Spek minimal",
        "merek": None,
        "tipe": None,
        "nilai_tkdn": None,
        "kode_hs": None,
        "kbli": None,
        "kelompok_barang": None,
        "alamat": None,
        "provinsi": None,
        "masa_berlaku_akhir": None,
        "tahun_sumber": 2026,
    }
    stats = merge_and_upsert(db_conn, [row])
    assert stats["inserted"] >= 1


def test_fts_index_populated_after_insert(db_conn: sqlite3.Connection) -> None:
    merge_and_upsert(db_conn, [SAMPLE_ROW])

    result = db_conn.execute(
        "SELECT rowid FROM tkdn_search WHERE tkdn_search MATCH 'pompa'"
    ).fetchall()
    assert len(result) >= 1
