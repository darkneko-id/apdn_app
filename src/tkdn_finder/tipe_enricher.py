# src/tkdn_finder/tipe_enricher.py
"""Scrape Tipe data from tkdn.kemenperin.go.id/search.php per company or product."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

from .constants import DEFAULT_USER_AGENT

logger = logging.getLogger(__name__)

TKDN_SEARCH_URL = "https://tkdn.kemenperin.go.id/search.php"
TKDN_BASE_URL = "https://tkdn.kemenperin.go.id"


async def scrape_tipe_for_company(
    company_name: str,
    verify_ssl: bool = True,
    delay_seconds: float = 0.5,
) -> list[dict[str, Any]]:
    """Scrape all pages from tkdn.kemenperin.go.id for a company name.

    Returns list of dicts with keys:
        produk, spesifikasi, tipe, merek, kelompok_barang, nilai_tkdn_str
    """
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    results: list[dict[str, Any]] = []
    page = 1
    next_path: str | None = None

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=20, verify=verify_ssl
    ) as client:
        while True:
            if next_path:
                url = TKDN_BASE_URL + "/" + next_path.lstrip("/")
                r = await client.get(url, headers=headers)
            else:
                r = await client.get(
                    TKDN_SEARCH_URL,
                    params={"where": "perush", "what": company_name},
                    headers=headers,
                )

            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            table = soup.find("table")
            if not table:
                break

            rows = table.find_all("tr")[1:]  # skip header
            if not rows:
                break

            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) < 7:
                    continue
                # Columns: No | Perusahaan | Kelompok Barang | Jenis Produk
                #          | Spesifikasi | Tipe | Merk | Nilai TKDN
                results.append({
                    "nama_perusahaan": cells[1],
                    "kelompok_barang": cells[2],
                    "nama_produk": cells[3],
                    "spesifikasi": cells[4],
                    "tipe": cells[5] if cells[5] not in ("-", "") else "",
                    "merek": cells[6] if cells[6] not in ("-", "") else "",
                    "nilai_tkdn_str": cells[7].replace("%", "").strip() if len(cells) > 7 else "",
                })

            # Find link to next page
            next_link = None
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "hal=" in href:
                    txt = a.get_text(strip=True)
                    if txt.isdigit() and int(txt) == page + 1:
                        next_link = href
                        break

            if not next_link:
                break

            next_path = next_link
            page += 1
            await asyncio.sleep(delay_seconds)

    logger.info("Scraped %d rows for company=%r (%d pages)", len(results), company_name, page)
    return results


async def scrape_and_enrich_for_query(
    conn: sqlite3.Connection,
    query: str,
    search_by: str = "perush",
    verify_ssl: bool = True,
) -> dict[str, int]:
    """Scrape search.php with a query and enrich Tipe for all matching companies.

    search_by: 'perush' (company name) or 'produk' (product name).
    """
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    all_rows: list[dict[str, Any]] = []
    page = 1
    next_path: str | None = None

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=20, verify=verify_ssl
    ) as client:
        while True:
            if next_path:
                url = TKDN_BASE_URL + "/" + next_path.lstrip("/")
                r = await client.get(url, headers=headers)
            else:
                r = await client.get(
                    TKDN_SEARCH_URL,
                    params={"where": search_by, "what": query},
                    headers=headers,
                )

            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            table = soup.find("table")
            if not table:
                break

            page_rows = table.find_all("tr")[1:]
            if not page_rows:
                break

            for row in page_rows:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) < 7:
                    continue
                all_rows.append({
                    "nama_perusahaan": cells[1],
                    "kelompok_barang": cells[2],
                    "nama_produk": cells[3],
                    "spesifikasi": cells[4],
                    "tipe": cells[5] if cells[5] not in ("-", "") else "",
                    "merek": cells[6] if cells[6] not in ("-", "") else "",
                    "nilai_tkdn_str": cells[7].replace("%", "").strip() if len(cells) > 7 else "",
                })

            next_link = None
            for a in soup.find_all("a", href=True):
                if "hal=" in a["href"]:
                    txt = a.get_text(strip=True)
                    if txt.isdigit() and int(txt) == page + 1:
                        next_link = a["href"]
                        break
            if not next_link:
                break
            next_path = next_link
            page += 1
            await asyncio.sleep(0.5)

    # Group by company name, then enrich each group
    from collections import defaultdict
    by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        by_company[row["nama_perusahaan"]].append(row)

    total: dict[str, int] = {"updated": 0, "inserted": 0, "skipped": 0, "companies": 0}
    for company, rows in by_company.items():
        # Try exact match first, then fuzzy (ignore dots/spaces)
        db_name = _resolve_db_company_name(conn, company)
        if not db_name:
            total["skipped"] += len(rows)
            continue
        stats = enrich_tipe_in_db(conn, db_name, rows)
        total["updated"] += stats["updated"]
        total["inserted"] += stats["inserted"]
        total["skipped"] += stats["skipped"]
        total["companies"] += 1

    return total


def _resolve_db_company_name(conn: sqlite3.Connection, website_name: str) -> str | None:
    """Find the exact DB company name matching a website company name.

    Tries exact match first, then strips dots/extra spaces for fuzzy match.
    """
    # Exact match
    row = conn.execute(
        "SELECT nama_perusahaan FROM tkdn_certificate WHERE nama_perusahaan = ? LIMIT 1",
        (website_name,),
    ).fetchone()
    if row:
        return row[0]

    # Normalised match: collapse "PT." → "PT", strip extra spaces
    normalized = website_name.replace(".", "").replace("  ", " ").strip()
    row = conn.execute(
        "SELECT nama_perusahaan FROM tkdn_certificate "
        "WHERE REPLACE(REPLACE(nama_perusahaan,'.',''),'  ',' ') = ? LIMIT 1",
        (normalized,),
    ).fetchone()
    return row[0] if row else None


def enrich_tipe_in_db(
    conn: sqlite3.Connection,
    company_name: str,
    scraped_rows: list[dict[str, Any]],
) -> dict[str, int]:
    """Match scraped rows to DB entries and upsert Tipe data.

    Matching: (nama_produk, spesifikasi, nilai_tkdn rounded to 2dp).
    For existing rows with tipe='': UPDATE tipe.
    For rows not in DB (new Tipe variants): INSERT as new records.
    """
    stats = {"updated": 0, "inserted": 0, "skipped": 0}
    now_str = datetime.now(timezone.utc).isoformat()

    for row in scraped_rows:
        try:
            tkdn_val: float | None = float(row["nilai_tkdn_str"]) if row["nilai_tkdn_str"] else None
        except ValueError:
            tkdn_val = None

        tipe = row.get("tipe") or ""
        spesifikasi = row.get("spesifikasi") or ""
        nama_produk = row.get("nama_produk") or ""

        if not nama_produk:
            continue

        # Try to find existing row with same (company, product, spec, tkdn_value)
        # that has tipe='' (not yet enriched)
        existing = None
        if tkdn_val is not None:
            existing = conn.execute(
                """SELECT id, tipe FROM tkdn_certificate
                   WHERE nama_perusahaan = ?
                     AND nama_produk = ?
                     AND spesifikasi = ?
                     AND tipe = ''
                     AND ABS(COALESCE(nilai_tkdn, -999) - ?) < 0.1
                   LIMIT 1""",
                (company_name, nama_produk, spesifikasi, tkdn_val),
            ).fetchone()

        if existing and tipe:
            # Check if target (company, prod, spec, tipe) already exists from a
            # previous enrichment — if so, just remove the stale empty-tipe row.
            already = conn.execute(
                "SELECT 1 FROM tkdn_certificate "
                "WHERE nama_perusahaan=? AND nama_produk=? AND spesifikasi=? AND tipe=?",
                (company_name, nama_produk, spesifikasi, tipe),
            ).fetchone()
            if already:
                conn.execute("DELETE FROM tkdn_certificate WHERE id=?", (existing["id"],))
                stats["skipped"] += 1
            else:
                conn.execute(
                    "UPDATE tkdn_certificate SET tipe=?, ingested_at=? WHERE id=?",
                    (tipe, now_str, existing["id"]),
                )
                stats["updated"] += 1

        elif tipe:
            # Check if this exact (company, product, spec, tipe) already exists
            duplicate = conn.execute(
                """SELECT 1 FROM tkdn_certificate
                   WHERE nama_perusahaan = ? AND nama_produk = ?
                     AND spesifikasi = ? AND tipe = ?""",
                (company_name, nama_produk, spesifikasi, tipe),
            ).fetchone()

            if duplicate:
                stats["skipped"] += 1
                continue

            # Insert new row for this Tipe variant
            db_row = conn.execute(
                """SELECT * FROM tkdn_certificate
                   WHERE nama_perusahaan = ? AND nama_produk = ? AND spesifikasi = ?
                   LIMIT 1""",
                (company_name, nama_produk, spesifikasi),
            ).fetchone()

            if db_row:
                # Clone existing row with new Tipe
                conn.execute(
                    """INSERT OR IGNORE INTO tkdn_certificate
                       (nama_perusahaan, nama_produk, spesifikasi, merek, tipe,
                        nilai_tkdn, kode_hs, kbli, kelompok_barang, alamat, provinsi,
                        masa_berlaku_akhir, tahun_sumber, ingested_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        company_name, nama_produk, spesifikasi,
                        row.get("merek") or db_row["merek"],
                        tipe,
                        tkdn_val if tkdn_val is not None else db_row["nilai_tkdn"],
                        db_row["kode_hs"], db_row["kbli"],
                        row.get("kelompok_barang") or db_row["kelompok_barang"],
                        db_row["alamat"], db_row["provinsi"],
                        db_row["masa_berlaku_akhir"], db_row["tahun_sumber"],
                        now_str,
                    ),
                )
                stats["inserted"] += 1
            else:
                stats["skipped"] += 1

    conn.commit()
    return stats
