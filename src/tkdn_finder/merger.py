# src/tkdn_finder/merger.py
"""Merge parsed certificate rows into the database with upsert semantics."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


def merge_and_upsert(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> dict[str, int]:
    """Upsert parsed rows into tkdn_certificate.

    Uses INSERT OR REPLACE semantics tied to the UNIQUE(nama_perusahaan, nama_produk, spesifikasi)
    constraint. Tracks inserted vs updated counts.

    Args:
        conn: SQLite connection (must be open with row_factory=sqlite3.Row).
        rows: Normalized row dicts from parser.parse_html_export().

    Returns:
        Dict with keys "inserted", "updated", "skipped".
    """
    from datetime import datetime, timezone

    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    now_str = datetime.now(timezone.utc).isoformat()

    insert_sql = """
        INSERT INTO tkdn_certificate
            (nama_perusahaan, nama_produk, spesifikasi, merek, tipe, nilai_tkdn,
             kode_hs, kbli, kelompok_barang, alamat, provinsi, masa_berlaku_akhir,
             tahun_sumber, ingested_at)
        VALUES
            (:nama_perusahaan, :nama_produk, :spesifikasi, :merek, :tipe, :nilai_tkdn,
             :kode_hs, :kbli, :kelompok_barang, :alamat, :provinsi, :masa_berlaku_akhir,
             :tahun_sumber, :ingested_at)
        ON CONFLICT(nama_perusahaan, nama_produk, spesifikasi, merek, nilai_tkdn) DO UPDATE SET
            tipe = CASE WHEN excluded.tipe != '' THEN excluded.tipe ELSE tipe END,
            kode_hs = excluded.kode_hs,
            kbli = excluded.kbli,
            kelompok_barang = excluded.kelompok_barang,
            alamat = excluded.alamat,
            provinsi = excluded.provinsi,
            masa_berlaku_akhir = excluded.masa_berlaku_akhir,
            tahun_sumber = excluded.tahun_sumber,
            ingested_at = excluded.ingested_at
    """

    for row in rows:
        try:
            # spesifikasi and tipe are NOT NULL in schema; coerce None → ''
            # so the ON CONFLICT dedup key stays functional across re-ingests.
            row_with_ts = {
                **row,
                "ingested_at": now_str,
                "spesifikasi": row.get("spesifikasi") or "",
                "tipe": row.get("tipe") or "",
                "merek": row.get("merek") or "",
            }
            before_rowid = conn.execute("SELECT MAX(id) FROM tkdn_certificate").fetchone()[0] or 0
            conn.execute(insert_sql, row_with_ts)
            after_rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            if after_rowid > before_rowid:
                stats["inserted"] += 1
            else:
                stats["updated"] += 1
        except sqlite3.IntegrityError as exc:
            logger.warning(
                "Integrity error upserting row",
                extra={
                    "error": str(exc),
                    "nama_perusahaan": row.get("nama_perusahaan", ""),
                    "nama_produk": row.get("nama_produk", ""),
                },
            )
            stats["skipped"] += 1
        except Exception as exc:
            logger.exception(
                "Unexpected error upserting row",
                extra={"error": str(exc)},
            )
            stats["skipped"] += 1

    try:
        conn.commit()
    except sqlite3.Error as exc:
        logger.exception("Failed to commit transaction", extra={"error": str(exc)})
        raise

    logger.info(
        "Merge complete: inserted=%d updated=%d skipped=%d",
        stats["inserted"],
        stats["updated"],
        stats["skipped"],
    )
    return stats
