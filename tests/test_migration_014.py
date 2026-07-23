"""Migration 014 — canonicalise legal-entity prefixes in existing rows.

Applies migrations 001..013, inserts legacy rows with inconsistent prefix
spellings, then applies 014 and asserts the SQL canonicalisation matches
textnorm.normalize_company_name and merges rows that become identical.
"""

from __future__ import annotations

import sqlite3

import pytest

from tkdn_finder.db import _MIGRATION_DIR
from tkdn_finder.textnorm import normalize_company_name


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if not exists:
        return set()
    return {r[0] for r in conn.execute("SELECT version FROM schema_version").fetchall()}


def _apply_through(conn: sqlite3.Connection, last_version: int) -> None:
    applied = _applied_versions(conn)
    for path in sorted(_MIGRATION_DIR.glob("*.sql")):
        version = int(path.name.split("_")[0])
        if version > last_version or version in applied:
            continue
        conn.executescript(path.read_text(encoding="utf-8"))


def _insert(conn: sqlite3.Connection, name: str, produk: str, tipe: str = "") -> None:
    conn.execute(
        "INSERT INTO tkdn_certificate "
        "(nama_perusahaan, nama_produk, spesifikasi, merek, tipe, nilai_tkdn) "
        "VALUES (?, ?, '', '', ?, 40.0)",
        (name, produk, tipe),
    )


@pytest.fixture()
def db_at_013() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _apply_through(conn, 13)
    yield conn  # type: ignore[misc]
    conn.close()


def test_dotted_and_plain_prefix_merge(db_at_013: sqlite3.Connection) -> None:
    _insert(db_at_013, "PT. Bumi Kaya Steel", "Pipa")
    _insert(db_at_013, "PT Bumi Kaya Steel", "Pipa")  # duplicate once canonicalised
    db_at_013.commit()

    _apply_through(db_at_013, 14)

    rows = db_at_013.execute(
        "SELECT nama_perusahaan FROM tkdn_certificate"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["nama_perusahaan"] == "PT Bumi Kaya Steel"


def test_sql_matches_python_normalisation(db_at_013: sqlite3.Connection) -> None:
    samples = [
        "PT. Artas Energi Petrogas",
        "pt.  bumi kaya steel",
        "CV.Maju Jaya",
        "UD Sumber Rejeki",
        "PD. Karya Baru",
        "Fa. Sinar Abadi",
        "NV Dwi Warna",
        "PTPN Nusantara",  # fused — not a prefix
        "Koperasi Serba Usaha",  # no recognised prefix
    ]
    for i, name in enumerate(samples):
        _insert(db_at_013, name, f"Produk {i}")
    db_at_013.commit()

    _apply_through(db_at_013, 14)

    stored = {
        r["nama_produk"]: r["nama_perusahaan"]
        for r in db_at_013.execute(
            "SELECT nama_produk, nama_perusahaan FROM tkdn_certificate"
        ).fetchall()
    }
    for i, name in enumerate(samples):
        assert stored[f"Produk {i}"] == normalize_company_name(name)


def test_distinct_tipe_variants_survive_merge(db_at_013: sqlite3.Connection) -> None:
    # Same company (dot vs no dot) but different tipe → NOT duplicates.
    _insert(db_at_013, "PT. Bumi Kaya Steel", "Pipa", tipe="A")
    _insert(db_at_013, "PT Bumi Kaya Steel", "Pipa", tipe="B")
    db_at_013.commit()

    _apply_through(db_at_013, 14)

    rows = db_at_013.execute(
        "SELECT DISTINCT nama_perusahaan FROM tkdn_certificate"
    ).fetchall()
    assert db_at_013.execute("SELECT COUNT(*) FROM tkdn_certificate").fetchone()[0] == 2
    assert len(rows) == 1  # unified under one company name
