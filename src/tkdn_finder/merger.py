# src/tkdn_finder/merger.py
"""Merge parsed certificate rows into the database with upsert semantics."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from .textnorm import normalize_company_name

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
        ON CONFLICT(nama_perusahaan, nama_produk, spesifikasi, merek, nilai_tkdn, tipe) DO UPDATE SET
            kode_hs = excluded.kode_hs,
            kbli = excluded.kbli,
            kelompok_barang = excluded.kelompok_barang,
            alamat = excluded.alamat,
            provinsi = excluded.provinsi,
            masa_berlaku_akhir = excluded.masa_berlaku_akhir,
            tahun_sumber = excluded.tahun_sumber,
            ingested_at = excluded.ingested_at
    """

    # SQL for updating metadata on enriched rows when P3DN re-imports a tipe=''
    # bulk row. Enrichment (Update Tipe) may have backfilled tipe AND/OR merek
    # onto the stored row, so:
    #   - an empty excel merek must match any stored merek (backfilled), while
    #     a non-empty excel merek still requires equality;
    #   - rows enriched in EITHER field count (tipe != '' OR merek differs);
    #     rows identical in both are left to the INSERT's ON CONFLICT clause.
    # Without this, every scheduled re-download would re-insert the redundant
    # tipe=''/merek='' row next to its enriched version.
    _update_enriched_sql = """
        UPDATE tkdn_certificate SET
            kode_hs = :kode_hs,
            kbli = :kbli,
            kelompok_barang = :kelompok_barang,
            alamat = :alamat,
            provinsi = :provinsi,
            masa_berlaku_akhir = :masa_berlaku_akhir,
            tahun_sumber = :tahun_sumber,
            ingested_at = :ingested_at
        WHERE nama_perusahaan = :nama_perusahaan
          AND nama_produk = :nama_produk
          AND spesifikasi = :spesifikasi
          AND (merek = :merek OR :merek = '')
          AND ABS(COALESCE(nilai_tkdn, -999) - COALESCE(:nilai_tkdn, -999)) < 0.1
          AND (tipe != '' OR merek != :merek)
    """

    for row in rows:
        try:
            # spesifikasi and tipe are NOT NULL in schema; coerce None → ''
            # so the ON CONFLICT dedup key stays functional across re-ingests.
            # nama_perusahaan is canonicalised here (the dedup choke point) so
            # "PT. Bumi Kaya" and "PT Bumi Kaya" collapse to one company row.
            row_with_ts = {
                **row,
                "ingested_at": now_str,
                "nama_perusahaan": normalize_company_name(row.get("nama_perusahaan")),
                "spesifikasi": row.get("spesifikasi") or "",
                "tipe": row.get("tipe") or "",
                "merek": row.get("merek") or "",
            }

            # P3DN bulk rows always have tipe=''. If enriched tipe variants already
            # exist for the same (company, produk, spec, merek, nilai_tkdn), update
            # their metadata in-place rather than inserting a redundant tipe='' row.
            if not row_with_ts["tipe"]:
                cur = conn.execute(_update_enriched_sql, row_with_ts)
                if cur.rowcount > 0:
                    stats["updated"] += cur.rowcount
                    continue

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
