# src/tkdn_finder/p3dn_search_scraper.py
"""Scrape P3DN search.php to import products missing from the bulk export."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import date, datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from .constants import DEFAULT_USER_AGENT, P3DN_BASE_URL, P3DN_SEARCH_URL

logger = logging.getLogger(__name__)

# Maps header text variants → internal field name
_HEADER_ALIASES: dict[str, str] = {
    "perusahaan": "nama_perusahaan",
    "nama perusahaan": "nama_perusahaan",
    "produk": "nama_produk",
    "nama produk": "nama_produk",
    "jenis produk": "nama_produk",
    "spesifikasi": "spesifikasi",
    "nilai tkdn": "nilai_tkdn",
    "tkdn (%)": "nilai_tkdn",
    "tkdn": "nilai_tkdn",
    "berlaku s.d": "masa_berlaku_akhir",
    "masa berlaku": "masa_berlaku_akhir",
    "kelompok barang": "kelompok_barang",
    "kelompok": "kelompok_barang",
}


def _detect_columns(rows: list[Tag]) -> tuple[dict[str, int], int]:
    """Scan the first few rows for a recognizable header.

    Returns (col_map, first_data_row_index). col_map may be empty if no
    recognizable header is found — callers should fall back to positional parsing.
    """
    for i, row in enumerate(rows[:4]):  # scan up to 4 rows for header
        col_map: dict[str, int] = {}
        cells = row.find_all(["th", "td"])
        for j, cell in enumerate(cells):
            text = cell.get_text(strip=True).lower()
            for alias, field in _HEADER_ALIASES.items():
                if alias in text and field not in col_map:
                    col_map[field] = j
                    break
        if "nama_produk" in col_map:
            return col_map, i + 1  # data starts after header row
    return {}, 1  # no header found; data likely starts at row 1


def _get_col(texts: list[str], col_map: dict[str, int], field: str) -> str | None:
    idx = col_map.get(field)
    if idx is not None and idx < len(texts):
        v = texts[idx].strip()
        return v if v else None
    return None


async def scrape_p3dn_search(
    company_name: str,
    verify_ssl: bool = True,
    delay_seconds: float = 0.5,
) -> list[dict[str, Any]]:
    """Scrape P3DN search.php for a company and return all product rows.

    Returns list of dicts: {nama_perusahaan, nama_produk, spesifikasi, nilai_tkdn,
    kelompok_barang, detail_url}
    """
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    results: list[dict[str, Any]] = []
    page = 1
    next_path: str | None = None

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=30, verify=verify_ssl
    ) as client:
        while page <= 20:  # safety pagination guard
            if next_path:
                url = P3DN_BASE_URL + "/" + next_path.lstrip("/")
                r = await client.get(url, headers=headers)
            else:
                r = await client.get(
                    P3DN_SEARCH_URL,
                    params={"where": "perush", "what": company_name},
                    headers=headers,
                )

            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            table = soup.find("table")
            if not table or not isinstance(table, Tag):
                break

            all_rows = table.find_all("tr")
            if len(all_rows) < 2:
                break

            col_map, data_start = _detect_columns(all_rows)

            # Positional fallback when header detection fails.
            # Common P3DN search.php layout (based on observed bulk export format):
            #   0=No, 1=Perusahaan, 2=Produk, 3=Spesifikasi, 4=Nilai TKDN, 5=Berlaku, 6=Aksi
            # OR (with kelompok column):
            #   0=No, 1=Perusahaan, 2=Kelompok, 3=Produk, 4=Spesifikasi, 5=Nilai TKDN
            # We pick the one that produces a non-empty produk from the first data row.
            if not col_map:
                first_data = all_rows[data_start] if data_start < len(all_rows) else None
                if first_data:
                    cells = [td.get_text(strip=True) for td in first_data.find_all("td")]
                    # Heuristic: find the first column that looks like a TKDN% (float 0-100)
                    tkdn_col: int | None = None
                    for ci, v in enumerate(cells):
                        try:
                            val = float(v.replace(",", ".").replace("%", "").strip())
                            if 0.0 <= val <= 100.0 and ci > 1:
                                tkdn_col = ci
                                break
                        except ValueError:
                            pass
                    if tkdn_col is not None:
                        # Assume: col 1=company, col (tkdn-1)=spec, col (tkdn-2)=produk (min col 2)
                        col_map = {
                            "nama_perusahaan": 1,
                            "nama_produk": max(2, tkdn_col - 2),
                            "spesifikasi": max(3, tkdn_col - 1) if tkdn_col > 2 else tkdn_col,
                            "nilai_tkdn": tkdn_col,
                        }
                        logger.info(
                            "P3DN column detection used heuristic fallback (tkdn_col=%d): %s",
                            tkdn_col, col_map,
                        )
                    else:
                        logger.warning(
                            "P3DN column detection failed for company=%r; "
                            "no TKDN-like column found. Row sample: %s",
                            company_name, cells[:8],
                        )

            for row in all_rows[data_start:]:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue

                # Extract link to detail page
                detail_url: str | None = None
                for cell in cells:
                    a = cell.find("a", href=True)
                    if a and isinstance(a, Tag) and "sertifikat_perush" in str(a.get("href", "")):
                        href = str(a["href"])
                        detail_url = P3DN_BASE_URL + "/" + href.lstrip("/")
                        break

                texts = [c.get_text(strip=True) for c in cells]

                produk = _get_col(texts, col_map, "nama_produk")
                if not produk:
                    continue

                tkdn_str = _get_col(texts, col_map, "nilai_tkdn") or ""
                nilai_tkdn: float | None = None
                if tkdn_str:
                    try:
                        nilai_tkdn = float(
                            tkdn_str.replace(",", ".").replace("%", "").strip()
                        )
                    except ValueError:
                        pass

                results.append({
                    "nama_perusahaan": _get_col(texts, col_map, "nama_perusahaan") or company_name,
                    "nama_produk": produk,
                    "spesifikasi": _get_col(texts, col_map, "spesifikasi") or "",
                    "nilai_tkdn": nilai_tkdn,
                    "kelompok_barang": _get_col(texts, col_map, "kelompok_barang"),
                    "detail_url": detail_url,
                })

            # Find next page link
            next_link: str | None = None
            for a in soup.find_all("a", href=True):
                if not isinstance(a, Tag):
                    continue
                href = str(a.get("href", ""))
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

    logger.info(
        "P3DN search scraped %d rows for company=%r (%d pages)",
        len(results), company_name, page,
    )
    return results


async def _scrape_p3dn_detail(
    detail_url: str,
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    """Fetch alamat from a P3DN certificate detail page."""
    try:
        r = await client.get(detail_url, headers={"User-Agent": DEFAULT_USER_AGENT})
        r.raise_for_status()
    except Exception as exc:
        logger.debug("P3DN detail fetch failed for %s: %s", detail_url, exc)
        return {}

    soup = BeautifulSoup(r.text, "lxml")
    result: dict[str, Any] = {}

    # Find "Alamat" label and its sibling/adjacent value cell
    for tag in soup.find_all(["td", "th", "dt", "label", "p"]):
        if not isinstance(tag, Tag):
            continue
        text = tag.get_text(strip=True).lower()
        if text in ("alamat", "alamat:"):
            sibling = tag.find_next_sibling(["td", "dd", "p"])
            if sibling and isinstance(sibling, Tag):
                alamat = sibling.get_text(strip=True)
                if alamat:
                    result["alamat"] = alamat
            break

    return result


def upsert_p3dn_rows(
    conn: sqlite3.Connection,
    db_company_name: str,
    rows: list[dict[str, Any]],
    today: date,
) -> dict[str, int]:
    """Match P3DN-scraped rows to DB entries and upsert p3dn_search_last_seen.

    For rows already in DB (from bulk export or enrichment): UPDATE last_seen.
    For rows absent from DB: INSERT as new records with masa_berlaku_akhir=NULL.
    Always uses db_company_name for DB operations (ignores scraped company name).
    """
    stats = {"updated": 0, "inserted": 0, "skipped": 0}
    today_str = today.isoformat()
    now_str = datetime.now(timezone.utc).isoformat()

    for row in rows:
        produk = row.get("nama_produk") or ""
        spec = row.get("spesifikasi") or ""
        nilai_tkdn = row.get("nilai_tkdn")

        if not produk:
            stats["skipped"] += 1
            continue

        # Match existing rows by (company, product, spec) with fuzzy tkdn tolerance
        if nilai_tkdn is not None:
            existing = conn.execute(
                """SELECT id FROM tkdn_certificate
                   WHERE nama_perusahaan = ? AND nama_produk = ? AND spesifikasi = ?
                     AND ABS(COALESCE(nilai_tkdn, -999) - ?) < 0.5""",
                (db_company_name, produk, spec, nilai_tkdn),
            ).fetchall()
        else:
            existing = conn.execute(
                """SELECT id FROM tkdn_certificate
                   WHERE nama_perusahaan = ? AND nama_produk = ? AND spesifikasi = ?""",
                (db_company_name, produk, spec),
            ).fetchall()

        if existing:
            for ex in existing:
                conn.execute(
                    "UPDATE tkdn_certificate SET p3dn_search_last_seen = ? WHERE id = ?",
                    (today_str, ex["id"]),
                )
            stats["updated"] += len(existing)
        else:
            # New product not in bulk export — insert minimal record from P3DN
            try:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO tkdn_certificate
                       (nama_perusahaan, nama_produk, spesifikasi, merek, tipe,
                        nilai_tkdn, kode_hs, kbli, kelompok_barang, alamat, provinsi,
                        masa_berlaku_akhir, tahun_sumber, ingested_at, p3dn_search_last_seen)
                       VALUES (?, ?, ?, '', '', ?, NULL, NULL, ?, ?, NULL, NULL, NULL, ?, ?)""",
                    (
                        db_company_name, produk, spec,
                        nilai_tkdn,
                        row.get("kelompok_barang"),
                        row.get("alamat"),
                        now_str,
                        today_str,
                    ),
                )
                if cur.rowcount > 0:
                    stats["inserted"] += 1
                else:
                    stats["skipped"] += 1
            except sqlite3.IntegrityError:
                logger.warning(
                    "IntegrityError inserting P3DN row: %s / %s", db_company_name, produk
                )
                stats["skipped"] += 1

    conn.commit()
    return stats


async def scrape_and_import_p3dn(
    conn: sqlite3.Connection,
    db_company_name: str,
    today: date,
    verify_ssl: bool = True,
    delay_seconds: float = 0.5,
) -> dict[str, int]:
    """Scrape P3DN search for a company and import any products missing from the DB.

    Uses db_company_name as the search query and as the key for all DB operations.
    """
    rows = await scrape_p3dn_search(db_company_name, verify_ssl, delay_seconds)
    if not rows:
        return {"updated": 0, "inserted": 0, "skipped": 0}

    # Enrich with alamat from detail pages (deduplicated by URL)
    seen_urls: set[str] = set()
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=30, verify=verify_ssl
    ) as client:
        for row in rows:
            detail_url = row.pop("detail_url", None)
            if detail_url and detail_url not in seen_urls:
                seen_urls.add(detail_url)
                detail = await _scrape_p3dn_detail(detail_url, client)
                if detail.get("alamat") and not row.get("alamat"):
                    row["alamat"] = detail["alamat"]
                await asyncio.sleep(delay_seconds)

    return upsert_p3dn_rows(conn, db_company_name, rows, today)
