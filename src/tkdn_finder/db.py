# src/tkdn_finder/db.py
"""SQLite connection helpers, schema init, and all SQL queries."""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MIGRATION_DIR = Path(__file__).parent.parent.parent / "migrations"

# --- Filter-list cache (kbli + year) invalidated after each bulk refresh ---
_kbli_cache: list[str] = []
_year_cache: list[int] = []
_filter_cache_dirty: bool = True


def invalidate_filter_cache() -> None:
    """Call after refresh_all_years completes to force reload on next request."""
    global _filter_cache_dirty
    _filter_cache_dirty = True


def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and row_factory."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(db_path_or_conn: str | sqlite3.Connection) -> None:
    """Apply migrations/001_initial.sql idempotently."""
    if isinstance(db_path_or_conn, str):
        conn = get_connection(db_path_or_conn)
        _apply_migrations(conn)
        conn.close()
    else:
        _apply_migrations(db_path_or_conn)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply all pending migrations in order."""
    migrations_dir = _MIGRATION_DIR
    if not migrations_dir.exists():
        migrations_dir = Path(__file__).parent.parent.parent / "migrations"

    applied = {
        row[0]
        for row in conn.execute(
            "SELECT version FROM schema_version"
        ).fetchall()
    } if _table_exists(conn, "schema_version") else set()

    for migration_file in sorted(migrations_dir.glob("*.sql")):
        # Extract version number from filename prefix (e.g. "001_initial.sql" → 1)
        try:
            version = int(migration_file.name.split("_")[0])
        except ValueError:
            continue
        if version in applied:
            continue
        sql = migration_file.read_text(encoding="utf-8")
        conn.executescript(sql)
        logger.info("Applied migration %s", migration_file.name)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def get_db_path(data_dir: str = "data") -> str:
    """Compute the SQLite database path."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        base = os.path.join(appdata, "TKDN-Finder")
    else:
        base = data_dir
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "tkdn.db")


def upsert_certificate(conn: sqlite3.Connection, row: dict[str, Any]) -> str:
    """Insert or replace a certificate row. Returns 'inserted' or 'updated'."""
    sql = """
        INSERT INTO tkdn_certificate
            (nama_perusahaan, nama_produk, spesifikasi, merek, tipe, nilai_tkdn,
             kode_hs, kbli, kelompok_barang, alamat, provinsi, masa_berlaku_akhir,
             tahun_sumber, ingested_at)
        VALUES
            (:nama_perusahaan, :nama_produk, :spesifikasi, :merek, :tipe, :nilai_tkdn,
             :kode_hs, :kbli, :kelompok_barang, :alamat, :provinsi, :masa_berlaku_akhir,
             :tahun_sumber, :ingested_at)
        ON CONFLICT(nama_perusahaan, nama_produk, spesifikasi, tipe) DO UPDATE SET
            merek = excluded.merek,
            nilai_tkdn = excluded.nilai_tkdn,
            kode_hs = excluded.kode_hs,
            kbli = excluded.kbli,
            kelompok_barang = excluded.kelompok_barang,
            alamat = excluded.alamat,
            provinsi = excluded.provinsi,
            masa_berlaku_akhir = excluded.masa_berlaku_akhir,
            tahun_sumber = excluded.tahun_sumber,
            ingested_at = excluded.ingested_at
    """
    now_str = datetime.now(timezone.utc).isoformat()
    row = {**row, "ingested_at": now_str}
    cursor = conn.execute(sql, row)
    # lastrowid changes only on insert; use changes() to detect update
    return "inserted" if cursor.lastrowid and conn.execute("SELECT changes()").fetchone()[0] == 1 else "updated"


def save_download_run(
    conn: sqlite3.Connection,
    year: str,
    url: str,
    status: str,
    started_at: datetime,
    finished_at: datetime,
    row_count: int | None = None,
    error_message: str | None = None,
) -> None:
    """Persist a download run record."""
    conn.execute(
        """
        INSERT INTO download_run
            (year_label, source_url, status, started_at, finished_at, row_count, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (year, url, status, started_at.isoformat(), finished_at.isoformat(), row_count, error_message),
    )
    conn.commit()


def get_download_runs(conn: sqlite3.Connection, limit: int = 10) -> list[sqlite3.Row]:
    """Return last N download run records."""
    cursor = conn.execute(
        "SELECT * FROM download_run ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return cursor.fetchall()


def get_cached_urls(conn: sqlite3.Connection) -> dict[str, str]:
    """Return {year_label: source_url} from last successful run per year."""
    cursor = conn.execute(
        """
        SELECT year_label, source_url
        FROM download_run
        WHERE status = 'success' AND source_url IS NOT NULL
        GROUP BY year_label
        HAVING id = MAX(id)
        """
    )
    return {row["year_label"]: row["source_url"] for row in cursor.fetchall()}


def get_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return summary statistics from the database."""
    total = conn.execute("SELECT COUNT(*) FROM tkdn_certificate").fetchone()[0]
    last_run = conn.execute(
        "SELECT finished_at FROM download_run WHERE status='success' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    last_refresh = last_run["finished_at"] if last_run else None

    rows_per_year = {}
    cursor = conn.execute(
        "SELECT tahun_sumber, COUNT(*) AS cnt FROM tkdn_certificate GROUP BY tahun_sumber ORDER BY tahun_sumber"
    )
    for row in cursor.fetchall():
        rows_per_year[str(row["tahun_sumber"])] = row["cnt"]

    return {
        "total_rows": total,
        "last_refresh": last_refresh,
        "rows_per_year": rows_per_year,
    }


def get_certificate_by_id(conn: sqlite3.Connection, cert_id: int) -> sqlite3.Row | None:
    """Fetch a single certificate by primary key."""
    cursor = conn.execute(
        "SELECT * FROM tkdn_certificate WHERE id = ?",
        (cert_id,),
    )
    return cursor.fetchone()


def _fetch_kbli_list(conn: sqlite3.Connection) -> list[str]:
    cursor = conn.execute(
        "SELECT DISTINCT kbli FROM tkdn_certificate "
        "WHERE kbli IS NOT NULL AND kbli GLOB '[0-9][0-9][0-9][0-9][0-9]' "
        "ORDER BY kbli"
    )
    return [row["kbli"] for row in cursor.fetchall()]


def _fetch_year_list(conn: sqlite3.Connection) -> list[int]:
    cursor = conn.execute(
        "SELECT DISTINCT tahun_sumber FROM tkdn_certificate WHERE tahun_sumber IS NOT NULL ORDER BY tahun_sumber"
    )
    return [row["tahun_sumber"] for row in cursor.fetchall()]


def get_kbli_list(conn: sqlite3.Connection) -> list[str]:
    """Return distinct valid KBLI codes. Cached in memory until invalidated."""
    global _kbli_cache, _year_cache, _filter_cache_dirty
    if _filter_cache_dirty:
        _kbli_cache = _fetch_kbli_list(conn)
        _year_cache = _fetch_year_list(conn)
        _filter_cache_dirty = False
    return _kbli_cache


def get_year_list(conn: sqlite3.Connection) -> list[int]:
    """Return distinct non-null source years. Cached in memory until invalidated."""
    global _kbli_cache, _year_cache, _filter_cache_dirty
    if _filter_cache_dirty:
        _kbli_cache = _fetch_kbli_list(conn)
        _year_cache = _fetch_year_list(conn)
        _filter_cache_dirty = False
    return _year_cache


def get_synonyms_all(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return all synonym rows."""
    cursor = conn.execute("SELECT * FROM synonym ORDER BY canonical")
    return cursor.fetchall()


def upsert_synonym(conn: sqlite3.Connection, canonical: str, variants: str) -> None:
    """Insert or update a synonym entry."""
    conn.execute(
        """
        INSERT INTO synonym (canonical, variants, enabled)
        VALUES (?, ?, 1)
        ON CONFLICT(canonical) DO UPDATE SET variants = excluded.variants
        """,
        (canonical, variants),
    )
    conn.commit()


def delete_synonym(conn: sqlite3.Connection, synonym_id: int) -> None:
    """Delete a synonym by id."""
    conn.execute("DELETE FROM synonym WHERE id = ?", (synonym_id,))
    conn.commit()
