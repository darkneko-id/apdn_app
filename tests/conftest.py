"""Shared fixtures and helpers for all test modules."""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from tkdn_finder.db import init_db, invalidate_filter_cache
from tkdn_finder.search import invalidate_synonym_cache


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite DB with all migrations applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    yield conn  # type: ignore[misc]
    conn.close()


@pytest.fixture(autouse=True)
def _reset_module_caches() -> None:
    """Reset module-level caches before every test to prevent cross-test bleed."""
    invalidate_filter_cache()
    invalidate_synonym_cache()


@pytest.fixture()
def cert_factory() -> Any:
    """Return a factory that builds minimal valid certificate row dicts."""

    def _make(**kwargs: Any) -> dict[str, Any]:
        row: dict[str, Any] = {
            "nama_perusahaan": "PT Test Corp",
            "nama_produk": "Centrifugal Pump",
            "spesifikasi": "6 inch 200 GPM",
            "merek": "BrandX",
            "tipe": "",
            "nilai_tkdn": 40.0,
            "kode_hs": "8413.11",
            "kbli": "28101",
            "kelompok_barang": "Pompa",
            "alamat": "Jl. Industri No. 1, Jakarta",
            "provinsi": "DKI Jakarta",
            "masa_berlaku_akhir": "2027-12-31",
            "tahun_sumber": 2025,
        }
        row.update(kwargs)
        return row

    return _make
