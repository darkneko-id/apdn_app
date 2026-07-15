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

from .constants import (
    DEFAULT_USER_AGENT,
    P3DN_BASE_URL,
    P3DN_SEARCH_DETAIL_FETCH_CONCURRENCY,
    P3DN_SEARCH_TKDN_MATCH_TOLERANCE,
    P3DN_SEARCH_URL,
)
from .textnorm import clean_cell_text, equivalent_text_indices, match_key

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
    "tipe": "tipe",
    "merk": "merek",
    "merek": "merek",
}

# Placeholder cell values the site renders for "no data"
_EMPTY_CELL_VALUES = frozenset({"", "-", "–", "—", "−"})


def _cell_or_empty(value: str | None) -> str:
    v = (value or "").strip()
    return "" if v in _EMPTY_CELL_VALUES else v


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
        # Require at least 2 distinct field matches before treating a row as the
        # header — a single match (e.g. a product name that happens to contain
        # "produk") can otherwise misidentify a data row as the header and skip
        # every real data row that follows it.
        if "nama_produk" in col_map and len(col_map) >= 2:
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
    base_params = {"where": "perush", "what": company_name}

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=30, verify=verify_ssl
    ) as client:
        while page <= 20:  # safety pagination guard
            # Always re-issue the original search params plus the page number —
            # following a bare href from the page (e.g. "search.php?hal=2") can
            # drop the where/what filter if P3DN's pagination links omit it,
            # causing unfiltered results to be attributed to this company.
            params = dict(base_params) if page == 1 else {**base_params, "hal": str(page)}
            r = await client.get(P3DN_SEARCH_URL, params=params, headers=headers)

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
                        # Assume col 1=company. Only assign produk/spesifikasi to columns
                        # that exist and don't collide with tkdn_col or each other.
                        if tkdn_col - 2 >= 2:
                            # room for company, produk, spec before the tkdn column
                            col_map = {
                                "nama_perusahaan": 1,
                                "nama_produk": tkdn_col - 2,
                                "spesifikasi": tkdn_col - 1,
                                "nilai_tkdn": tkdn_col,
                            }
                        elif tkdn_col - 1 >= 2:
                            # only room for produk; no distinct spec column
                            col_map = {
                                "nama_perusahaan": 1,
                                "nama_produk": tkdn_col - 1,
                                "nilai_tkdn": tkdn_col,
                            }
                        if col_map:
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

                # Separator + clean: nested tags/newlines inside a cell must not
                # glue words together or leave double spaces — stored rows from
                # the bulk export are whitespace-collapsed by the parser.
                texts = [clean_cell_text(c.get_text(" ", strip=True)) for c in cells]

                produk = _get_col(texts, col_map, "nama_produk")
                if not produk:
                    logger.debug(
                        "Skipping P3DN row with empty produk (page=%d col_map=%s): %s",
                        page, col_map, texts[:6],
                    )
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
                    # Tipe/Merk are part of the certificate's identity on
                    # search.php — rows can differ ONLY in these columns.
                    "tipe": _cell_or_empty(_get_col(texts, col_map, "tipe")),
                    "merek": _cell_or_empty(_get_col(texts, col_map, "merek")),
                    "detail_url": detail_url,
                })

            # Find next page link by looking for hal=N in href.
            # Avoid prefix matches: "hal=2" must not match "hal=20".
            next_link: str | None = None
            target_hal = f"hal={page + 1}"
            for a in soup.find_all("a", href=True):
                if not isinstance(a, Tag):
                    continue
                href = str(a.get("href", ""))
                idx = href.find(target_hal)
                if idx == -1:
                    continue
                after = href[idx + len(target_hal):]
                if not after or not after[0].isdigit():
                    next_link = href
                    break

            if not next_link:
                break

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

    Matching is whitespace-, case- and dash-insensitive (see textnorm.match_key):
    P3DN's search.php and the bulk export format the same certificate text
    differently, and an exact/TRIM-only comparison used to miss the row, insert
    a duplicate, and falsely mark the original as absent from P3DN.

    Tipe and Merk are part of a certificate's identity on search.php — rows
    can differ ONLY in those columns (the bulk export leaves tipe empty).
    A scraped tipe/merek is backfilled onto a matching empty-tipe/-merek row;
    a conflicting one means a distinct certificate and inserts a new row.
    """
    stats = {"updated": 0, "inserted": 0, "skipped": 0, "deduped": 0}
    today_str = today.isoformat()
    now_str = datetime.now(timezone.utc).isoformat()

    def _is_minimal(r: dict[str, Any]) -> bool:
        """True for skeleton rows this importer created (no bulk-export provenance).

        tahun_sumber/masa_berlaku_akhir are only ever set by the bulk-export
        parser or by tipe_enricher's variant-clone (which copies them from the
        sibling bulk row) — never by this importer. That makes them a reliable
        provenance marker, unlike tipe/merek, which this importer now scrapes
        from search.php (and which a pre-fix matching bug could also have set
        wrongly) — so tipe/merek being non-empty must NOT disqualify a row
        from being treated as the P3DN-only skeleton.
        """
        return r["tahun_sumber"] is None and r["masa_berlaku_akhir"] is None

    # Preload this company's rows once and index them by normalized
    # (produk, spesifikasi) key — SQL string functions can't express the
    # whitespace/dash-insensitive comparison we need.
    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for db_row in conn.execute(
        """SELECT id, nama_produk, spesifikasi, nilai_tkdn, merek, tipe,
                  tahun_sumber, masa_berlaku_akhir
           FROM tkdn_certificate WHERE nama_perusahaan = ?""",
        (db_company_name,),
    ).fetchall():
        key = (match_key(db_row["nama_produk"]), match_key(db_row["spesifikasi"]))
        index.setdefault(key, []).append(dict(db_row))

    deleted_ids: set[int] = set()

    for row in rows:
        produk = clean_cell_text(row.get("nama_produk") or "")
        spec = clean_cell_text(row.get("spesifikasi") or "")
        scraped_tipe = clean_cell_text(row.get("tipe") or "")
        scraped_merek = clean_cell_text(row.get("merek") or "")
        nilai_tkdn = row.get("nilai_tkdn")

        if not produk:
            stats["skipped"] += 1
            continue

        candidates = [
            r
            for r in index.get((match_key(produk), match_key(spec)), [])
            if r["id"] not in deleted_ids
        ]
        if not candidates and nilai_tkdn is not None:
            # Token-equivalence fallback: the excel export and search.php
            # sometimes word the same certificate differently ("Dia." vs
            # "Diameter", reordered product names), which defeats the
            # normalized key. Gated on same company + same TKDN so
            # distinct-but-similar certificates don't merge.
            pool = [
                r
                for rows_ in index.values()
                for r in rows_
                if r["id"] not in deleted_ids
                and r["nilai_tkdn"] is not None
                and abs(r["nilai_tkdn"] - nilai_tkdn) < P3DN_SEARCH_TKDN_MATCH_TOLERANCE
            ]
            hits = equivalent_text_indices(
                f"{produk} {spec}",
                [f"{r['nama_produk']} {r['spesifikasi']}" for r in pool],
            )
            candidates = [pool[i] for i in hits]
        if nilai_tkdn is not None:
            matches = [
                r
                for r in candidates
                if r["nilai_tkdn"] is not None
                and abs(r["nilai_tkdn"] - nilai_tkdn) < P3DN_SEARCH_TKDN_MATCH_TOLERANCE
            ]
        else:
            matches = candidates

        if matches:
            # Heal duplicates created by the old exact-text matching: if this
            # scraped row matches both a real (bulk-export/enriched) row and a
            # skeleton row previously inserted by this importer, the skeleton
            # is redundant — drop it, first rescuing any tipe/merek it carries
            # onto a rich row that lacks them.
            rich = [r for r in matches if not _is_minimal(r)]
            if rich and nilai_tkdn is not None:
                for r in list(matches):
                    if not _is_minimal(r):
                        continue
                    r_tipe_k = match_key(r["tipe"])
                    r_merek_k = match_key(r["merek"])
                    # Already represented by a rich row carrying the same
                    # tipe/merek (empty skeleton fields match anything)?
                    represented = any(
                        (not r_tipe_k or match_key(x["tipe"]) == r_tipe_k)
                        and (not r_merek_k or match_key(x["merek"]) == r_merek_k)
                        for x in rich
                    )
                    if not represented:
                        # Merge the skeleton's fields onto a rich row whose
                        # corresponding fields are empty (or already equal).
                        target = next(
                            (
                                x
                                for x in rich
                                if (
                                    not r_tipe_k
                                    or not (x["tipe"] or "")
                                    or match_key(x["tipe"]) == r_tipe_k
                                )
                                and (
                                    not r_merek_k
                                    or not (x["merek"] or "")
                                    or match_key(x["merek"]) == r_merek_k
                                )
                            ),
                            None,
                        )
                        if target is None:
                            # Deleting would lose the skeleton's tipe/merek —
                            # keep it; it now acts as a distinct variant row.
                            continue
                        if r_tipe_k and not (target["tipe"] or ""):
                            conn.execute(
                                "UPDATE tkdn_certificate SET tipe=? WHERE id=?",
                                (r["tipe"], target["id"]),
                            )
                            target["tipe"] = r["tipe"]
                        if r_merek_k and not (target["merek"] or ""):
                            conn.execute(
                                "UPDATE tkdn_certificate SET merek=? WHERE id=?",
                                (r["merek"], target["id"]),
                            )
                            target["merek"] = r["merek"]
                    conn.execute(
                        "DELETE FROM tkdn_certificate WHERE id = ?", (r["id"],)
                    )
                    deleted_ids.add(r["id"])
                    stats["deduped"] += 1
                matches = [r for r in matches if r["id"] not in deleted_ids]

        # search.php rows can differ ONLY in Tipe/Merk — those are distinct
        # certificates. Narrow the matches accordingly: prefer rows carrying
        # the same tipe; else backfill onto an empty-tipe row (that's exactly
        # what the Update Tipe button promises); else treat as a new variant.
        if matches and scraped_tipe:
            tipe_k = match_key(scraped_tipe)
            same_tipe = [r for r in matches if match_key(r["tipe"]) == tipe_k]
            if same_tipe:
                matches = same_tipe
            else:
                empty_tipe = [r for r in matches if not (r["tipe"] or "")]
                if not empty_tipe:
                    matches = []  # all matches carry a DIFFERENT tipe
                elif nilai_tkdn is None:
                    matches = empty_tipe  # too uncertain to backfill or fork
                else:
                    target = empty_tipe[0]
                    conn.execute(
                        "UPDATE tkdn_certificate SET tipe=? WHERE id=?",
                        (scraped_tipe, target["id"]),
                    )
                    target["tipe"] = scraped_tipe
                    matches = [target]

        if matches and scraped_merek:
            merek_k = match_key(scraped_merek)
            same_merek = [r for r in matches if match_key(r["merek"]) == merek_k]
            if same_merek:
                matches = same_merek
            else:
                empty_merek = [r for r in matches if not (r["merek"] or "")]
                if not empty_merek:
                    matches = []  # all matches carry a DIFFERENT merek
                elif nilai_tkdn is None:
                    matches = empty_merek
                else:
                    target = empty_merek[0]
                    conn.execute(
                        "UPDATE tkdn_certificate SET merek=? WHERE id=?",
                        (scraped_merek, target["id"]),
                    )
                    target["merek"] = scraped_merek
                    matches = [target]

        if matches:
            for ex in matches:
                conn.execute(
                    "UPDATE tkdn_certificate SET p3dn_search_last_seen = ? WHERE id = ?",
                    (today_str, ex["id"]),
                )
            stats["updated"] += len(matches)
        else:
            # New product not in bulk export — insert minimal record from P3DN
            try:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO tkdn_certificate
                       (nama_perusahaan, nama_produk, spesifikasi, merek, tipe,
                        nilai_tkdn, kode_hs, kbli, kelompok_barang, alamat, provinsi,
                        masa_berlaku_akhir, tahun_sumber, ingested_at, p3dn_search_last_seen)
                       VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, NULL, NULL, NULL, ?, ?)""",
                    (
                        db_company_name, produk, spec,
                        scraped_merek, scraped_tipe,
                        nilai_tkdn,
                        row.get("kelompok_barang"),
                        row.get("alamat"),
                        now_str,
                        today_str,
                    ),
                )
                if cur.rowcount > 0:
                    stats["inserted"] += 1
                    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    index.setdefault((match_key(produk), match_key(spec)), []).append({
                        "id": new_id,
                        "nama_produk": produk,
                        "spesifikasi": spec,
                        "nilai_tkdn": nilai_tkdn,
                        "merek": scraped_merek,
                        "tipe": scraped_tipe,
                        "tahun_sumber": None,
                        "masa_berlaku_akhir": None,
                    })
                else:
                    stats["skipped"] += 1
            except sqlite3.IntegrityError:
                logger.warning(
                    "IntegrityError inserting P3DN row: %s / %s", db_company_name, produk
                )
                stats["skipped"] += 1

    # After processing all scraped rows, mark records of this company that were NOT
    # found in this scrape (p3dn_search_last_seen not updated to today).
    # Only do this when the scrape returned results — empty scrapes should not
    # mark existing records as absent.
    if rows:
        conn.execute(
            "UPDATE tkdn_certificate SET p3dn_not_found_since = ? "
            "WHERE nama_perusahaan = ? "
            "  AND (p3dn_search_last_seen IS NULL OR p3dn_search_last_seen != ?) "
            "  AND p3dn_not_found_since IS NULL",
            (today_str, db_company_name, today_str),
        )
        conn.execute(
            "UPDATE tkdn_certificate SET p3dn_not_found_since = NULL "
            "WHERE nama_perusahaan = ? AND p3dn_search_last_seen = ?",
            (db_company_name, today_str),
        )

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

    # Enrich with alamat from detail pages, fetched concurrently (bounded) instead
    # of sequentially — a company with dozens of products would otherwise block
    # the request for tens of seconds (one GET + sleep per unique detail URL).
    detail_urls = [row.pop("detail_url", None) for row in rows]
    unique_urls = {u for u in detail_urls if u}

    if unique_urls:
        semaphore = asyncio.Semaphore(P3DN_SEARCH_DETAIL_FETCH_CONCURRENCY)
        details: dict[str, dict[str, Any]] = {}

        async def _fetch(client: httpx.AsyncClient, url: str) -> None:
            async with semaphore:
                details[url] = await _scrape_p3dn_detail(url, client)

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30, verify=verify_ssl
        ) as client:
            await asyncio.gather(*(_fetch(client, u) for u in unique_urls))

        for row, detail_url in zip(rows, detail_urls):
            if detail_url and details.get(detail_url, {}).get("alamat") and not row.get("alamat"):
                row["alamat"] = details[detail_url]["alamat"]

    return upsert_p3dn_rows(conn, db_company_name, rows, today)
