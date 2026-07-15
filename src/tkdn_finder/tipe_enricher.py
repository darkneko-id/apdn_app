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

from .constants import DEFAULT_USER_AGENT, TIPE_ENRICH_TKDN_MATCH_TOLERANCE
from .textnorm import clean_cell_text, match_key, parse_tkdn_percent

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
                cells = [
                    clean_cell_text(td.get_text(" ", strip=True))
                    for td in row.find_all("td")
                ]
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
                cells = [
                    clean_cell_text(td.get_text(" ", strip=True))
                    for td in row.find_all("td")
                ]
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

    from .db import resolve_company_name
    by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        by_company[row["nama_perusahaan"]].append(row)

    total: dict[str, int] = {"updated": 0, "inserted": 0, "skipped": 0, "companies": 0}
    for company, rows in by_company.items():
        # Try exact match first, then fuzzy (ignore dots/spaces)
        db_name = resolve_company_name(conn, company)
        if not db_name:
            total["skipped"] += len(rows)
            continue
        stats = enrich_tipe_in_db(conn, db_name, rows)
        total["updated"] += stats["updated"]
        total["inserted"] += stats["inserted"]
        total["skipped"] += stats["skipped"]
        total["companies"] += 1

    return total


def enrich_tipe_in_db(
    conn: sqlite3.Connection,
    company_name: str,
    scraped_rows: list[dict[str, Any]],
) -> dict[str, int]:
    """Match scraped rows to DB entries and upsert Tipe data.

    Matching is whitespace-, case- and dash-insensitive on (nama_produk,
    spesifikasi) — see textnorm.match_key — with nilai_tkdn tolerance.
    tkdn.kemenperin.go.id formats the same certificate text differently from
    the bulk export, so exact string comparison used to miss existing rows and
    insert duplicates instead of updating them.

    For existing rows with tipe='': UPDATE tipe.
    For rows not in DB (new Tipe variants): INSERT as new records.
    """
    stats = {"updated": 0, "inserted": 0, "skipped": 0, "deduped": 0}
    now_str = datetime.now(timezone.utc).isoformat()

    # Preload this company's rows, indexed by normalized (produk, spec) key.
    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for db_r in conn.execute(
        "SELECT * FROM tkdn_certificate WHERE nama_perusahaan = ?",
        (company_name,),
    ).fetchall():
        key = (match_key(db_r["nama_produk"]), match_key(db_r["spesifikasi"]))
        index.setdefault(key, []).append(dict(db_r))

    for row in scraped_rows:
        tkdn_val = parse_tkdn_percent(row.get("nilai_tkdn_str"))

        tipe = clean_cell_text(row.get("tipe") or "")
        spesifikasi = clean_cell_text(row.get("spesifikasi") or "")
        nama_produk = clean_cell_text(row.get("nama_produk") or "")

        if not nama_produk or not tipe:
            continue

        candidates = [
            c
            for c in index.get((match_key(nama_produk), match_key(spesifikasi)), [])
            if not c.get("_deleted")
        ]

        # Existing row with same (company, product, spec, tkdn_value) that has
        # tipe='' (not yet enriched)
        existing = None
        if tkdn_val is not None:
            existing = next(
                (
                    c
                    for c in candidates
                    if not (c["tipe"] or "")
                    and c["nilai_tkdn"] is not None
                    and abs(c["nilai_tkdn"] - tkdn_val) < TIPE_ENRICH_TKDN_MATCH_TOLERANCE
                ),
                None,
            )

        # Row that already carries this tipe (from a previous enrichment)
        tipe_key = match_key(tipe)
        already = next(
            (c for c in candidates if match_key(c["tipe"]) == tipe_key), None
        )

        if existing is not None:
            if already:
                # `already` carries this tipe already, but that doesn't always
                # mean it's the authoritative row: rows imported by the P3DN
                # search importer (upsert_p3dn_rows) start with tipe='' and no
                # bulk-export provenance (tahun_sumber IS NULL); a prior buggy
                # match could have set tipe on such a skeleton row instead of
                # on the real bulk-export row. Detect that by provenance —
                # only delete `existing` when `already` is itself a genuine
                # bulk-sourced/cloned variant (tahun_sumber IS NOT NULL).
                if already["tahun_sumber"] is None:
                    conn.execute(
                        "UPDATE tkdn_certificate SET tipe=?, ingested_at=? WHERE id=?",
                        (tipe, now_str, existing["id"]),
                    )
                    conn.execute(
                        "DELETE FROM tkdn_certificate WHERE id=?", (already["id"],)
                    )
                    existing["tipe"] = tipe
                    already["_deleted"] = True
                    stats["updated"] += 1
                    stats["deduped"] += 1
                else:
                    # Target tipe already exists as a proper cloned variant —
                    # just remove the stale empty-tipe row.
                    conn.execute("DELETE FROM tkdn_certificate WHERE id=?", (existing["id"],))
                    existing["_deleted"] = True
                    stats["skipped"] += 1
            else:
                conn.execute(
                    "UPDATE tkdn_certificate SET tipe=?, ingested_at=? WHERE id=?",
                    (tipe, now_str, existing["id"]),
                )
                existing["tipe"] = tipe
                stats["updated"] += 1

        else:
            if already:
                stats["skipped"] += 1
                continue

            # Insert new row for this Tipe variant, cloning metadata from any
            # sibling row of the same product. Use the sibling's stored text so
            # the DB keeps one canonical spelling per certificate.
            db_row = candidates[0] if candidates else None

            if db_row:
                # Clone existing row with new Tipe. INSERT OR IGNORE is idempotent:
                # if a previous enrichment run already inserted this exact tipe, skip.
                new_row = {
                    **db_row,
                    "merek": clean_cell_text(row.get("merek") or "") or db_row["merek"],
                    "tipe": tipe,
                    "nilai_tkdn": tkdn_val if tkdn_val is not None else db_row["nilai_tkdn"],
                    "kelompok_barang": clean_cell_text(row.get("kelompok_barang") or "")
                    or db_row["kelompok_barang"],
                    "ingested_at": now_str,
                }
                cur = conn.execute(
                    """INSERT OR IGNORE INTO tkdn_certificate
                       (nama_perusahaan, nama_produk, spesifikasi, merek, tipe,
                        nilai_tkdn, kode_hs, kbli, kelompok_barang, alamat, provinsi,
                        masa_berlaku_akhir, tahun_sumber, ingested_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        company_name, db_row["nama_produk"], db_row["spesifikasi"],
                        new_row["merek"],
                        tipe,
                        new_row["nilai_tkdn"],
                        db_row["kode_hs"], db_row["kbli"],
                        new_row["kelompok_barang"],
                        db_row["alamat"], db_row["provinsi"],
                        db_row["masa_berlaku_akhir"], db_row["tahun_sumber"],
                        now_str,
                    ),
                )
                if cur.rowcount > 0:
                    stats["inserted"] += 1
                    new_row["id"] = conn.execute(
                        "SELECT last_insert_rowid()"
                    ).fetchone()[0]
                    index.setdefault(
                        (match_key(db_row["nama_produk"]), match_key(db_row["spesifikasi"])),
                        [],
                    ).append(new_row)
                else:
                    stats["skipped"] += 1
            else:
                stats["skipped"] += 1

    conn.commit()
    return stats
