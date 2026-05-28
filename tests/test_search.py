# tests/test_search.py
"""Tests for the FTS5 search module."""

from __future__ import annotations

import sqlite3

import pytest

from tkdn_finder.merger import merge_and_upsert
from tkdn_finder.search import search
from tkdn_finder.synonyms import seed_default_synonyms


ROWS = [
    {
        "nama_perusahaan": "PT Pompa Nusantara",
        "nama_produk": "Pompa Sentrifugal",
        "spesifikasi": "Head 50m, kapasitas 100 m3/h",
        "merek": "NusaPump",
        "tipe": "NS-100",
        "nilai_tkdn": 42.5,
        "kode_hs": "84137090",
        "kbli": "28131",
        "kelompok_barang": "Pompa",
        "alamat": "Jakarta",
        "provinsi": "DKI Jakarta",
        "masa_berlaku_akhir": "2030-12-31",
        "tahun_sumber": 2026,
    },
    {
        "nama_perusahaan": "PT Kabel Listrik",
        "nama_produk": "Kabel Daya",
        "spesifikasi": "3x70mm2, 20kV XLPE",
        "merek": "SuperKabel",
        "tipe": "XLPE-70",
        "nilai_tkdn": 65.0,
        "kode_hs": "85444200",
        "kbli": "27320",
        "kelompok_barang": "Kabel",
        "alamat": "Surabaya",
        "provinsi": "Jawa Timur",
        "masa_berlaku_akhir": "2031-06-30",
        "tahun_sumber": 2025,
    },
    {
        "nama_perusahaan": "PT Trafo Indonesia",
        "nama_produk": "Transformer Distribusi",
        "spesifikasi": "100 kVA, 20kV/400V, ONAN",
        "merek": "TrafoPower",
        "tipe": "TD-100",
        "nilai_tkdn": 55.0,
        "kode_hs": "85042100",
        "kbli": "27110",
        "kelompok_barang": "Trafo",
        "alamat": "Bandung",
        "provinsi": "Jawa Barat",
        "masa_berlaku_akhir": "2024-01-01",  # expired
        "tahun_sumber": 2024,
    },
]


@pytest.fixture()
def search_db(db_conn: sqlite3.Connection) -> sqlite3.Connection:
    merge_and_upsert(db_conn, ROWS)
    seed_default_synonyms(db_conn)
    return db_conn


def test_search_basic_match(search_db: sqlite3.Connection) -> None:
    result = search(search_db, "pompa")
    assert result["total"] >= 1
    names = [r["nama_produk"] for r in result["results"]]
    assert any("Pompa" in n for n in names)


def test_search_multi_token(search_db: sqlite3.Connection) -> None:
    result = search(search_db, "kabel daya")
    assert result["total"] >= 1
    assert any("Kabel" in r["nama_produk"] for r in result["results"])


def test_search_empty_query_returns_all(search_db: sqlite3.Connection) -> None:
    result = search(search_db, "")
    assert result["total"] == len(ROWS)


def test_search_synonym_expansion(search_db: sqlite3.Connection) -> None:
    # "pump" should expand to "pompa" via default synonyms
    result = search(search_db, "pump")
    assert result["total"] >= 1
    assert any("Pompa" in r["nama_produk"] for r in result["results"])


def test_search_synonym_trafo(search_db: sqlite3.Connection) -> None:
    # "transformer" should expand to "trafo"
    result = search(search_db, "transformer")
    assert result["total"] >= 1


def test_search_tkdn_min_filter(search_db: sqlite3.Connection) -> None:
    result = search(search_db, "", tkdn_min=60.0)
    assert all((r["nilai_tkdn"] or 0) >= 60.0 for r in result["results"])


def test_search_validity_filter(search_db: sqlite3.Connection) -> None:
    result = search(search_db, "", validity_only=True)
    # Only rows with masa_berlaku_akhir >= today should appear
    from datetime import date
    today = date.today().isoformat()
    for r in result["results"]:
        assert r["masa_berlaku_akhir"] is not None
        assert r["masa_berlaku_akhir"] >= today


def test_search_kbli_filter(search_db: sqlite3.Connection) -> None:
    result = search(search_db, "", kbli="28131")
    assert result["total"] >= 1
    assert all(r["kbli"] == "28131" for r in result["results"])


def test_search_year_filter(search_db: sqlite3.Connection) -> None:
    result = search(search_db, "", year=2025)
    assert result["total"] >= 1
    assert all(r["tahun_sumber"] == 2025 for r in result["results"])


def test_search_pagination(search_db: sqlite3.Connection) -> None:
    result_page1 = search(search_db, "", limit=2, offset=0)
    result_page2 = search(search_db, "", limit=2, offset=2)
    assert len(result_page1["results"]) == 2
    ids_page1 = {r["id"] for r in result_page1["results"]}
    ids_page2 = {r["id"] for r in result_page2["results"]}
    assert ids_page1.isdisjoint(ids_page2)


def test_search_returns_query_time(search_db: sqlite3.Connection) -> None:
    result = search(search_db, "pompa")
    assert "query_time_ms" in result
    assert result["query_time_ms"] >= 0


def test_search_no_results(search_db: sqlite3.Connection) -> None:
    result = search(search_db, "xyznonexistentproduct12345")
    assert result["total"] == 0
    assert result["results"] == []
