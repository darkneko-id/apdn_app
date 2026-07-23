# src/tkdn_finder/routes/search.py
"""Search routes: GET / (HTML), GET /search (HTMX partial), GET /api/search (JSON)."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..config import Settings, get_settings
from ..constants import (
    SEARCH_DEBOUNCE_MS,
    SEARCH_RESULT_LIMIT_DEFAULT,
    SEARCH_RESULT_LIMIT_MAX,
    TKDN_DEFAULT_MIN_FILTER,
)
from ..db import get_connection, get_kbli_list, get_last_refresh_ts, get_year_list
from ..models import CertificateRow, SearchResponse, compute_validity_label
from ..search import search as do_search

logger = logging.getLogger(__name__)
router = APIRouter()


def _search_sync(
    db_path: str,
    query: str,
    tkdn_min: float,
    validity_only: bool,
    kbli: str | None,
    year_int: int | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    conn = get_connection(db_path)
    try:
        return do_search(
            conn=conn,
            query=query,
            tkdn_min=tkdn_min,
            validity_only=validity_only,
            kbli=kbli,
            year=year_int,
            limit=limit,
            offset=offset,
        )
    finally:
        conn.close()


def get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the main search page."""
    templates: Jinja2Templates = request.app.state.templates
    settings: Settings = get_settings()
    conn = get_connection(settings.get_db_path())
    try:
        kbli_list = get_kbli_list(conn)
        year_list = get_year_list(conn)
        last_refresh = get_last_refresh_ts(conn)
    finally:
        conn.close()

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "kbli_list": kbli_list,
            "year_list": year_list,
            "last_refresh": last_refresh,
            "debounce_ms": SEARCH_DEBOUNCE_MS,
        },
    )


_SORT_KEYS = {
    "perusahaan": lambda r: (r.nama_perusahaan or "").lower(),
    "produk":     lambda r: (r.nama_produk or "").lower(),
    "tkdn":       lambda r: r.nilai_tkdn or 0.0,
    "status":     lambda r: str(r.masa_berlaku_akhir or ""),
}


@router.get("/search", response_class=HTMLResponse)
async def search_htmx(
    request: Request,
    q: str = "",
    tkdn_min: float = TKDN_DEFAULT_MIN_FILTER,
    validity_only: bool = False,
    kbli: str | None = None,
    year: str | None = None,
    page: int = 1,
    limit: int = SEARCH_RESULT_LIMIT_DEFAULT,
    sort_by: str = "",
    sort_dir: str = "asc",
) -> HTMLResponse:
    """HTMX search endpoint — returns results.html partial."""
    templates: Jinja2Templates = request.app.state.templates
    settings: Settings = get_settings()
    limit = min(limit, SEARCH_RESULT_LIMIT_MAX)
    offset = (page - 1) * limit
    year_int: int | None = int(year) if year else None

    result = await asyncio.to_thread(
        _search_sync,
        settings.get_db_path(), q, tkdn_min, validity_only, kbli or None, year_int, limit, offset,
    )

    today = date.today()
    cert_rows = [CertificateRow.from_row(r, today) for r in result["results"]]

    # Apply explicit column sort (overrides relevance ranking)
    sort_key = _SORT_KEYS.get(sort_by)
    if sort_key:
        cert_rows.sort(key=sort_key, reverse=(sort_dir == "desc"))

    # Tag each row with validity status label
    tagged_rows = [
        (cert, compute_validity_label(cert, today))
        for cert in cert_rows
    ]

    total_pages = max(1, (result["total"] + limit - 1) // limit)

    return templates.TemplateResponse(
        request,
        "results.html",
        {
            "rows": tagged_rows,
            "total": result["total"],
            "query_time_ms": result["query_time_ms"],
            "q": q,
            "tkdn_min": tkdn_min,
            "validity_only": validity_only,
            "kbli": kbli,
            "year": year_int,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
        },
    )


@router.get("/api/search")
async def search_api(
    q: str = "",
    tkdn_min: float = TKDN_DEFAULT_MIN_FILTER,
    validity_only: bool = False,
    kbli: str | None = None,
    year: str | None = None,
    page: int = 1,
    limit: int = SEARCH_RESULT_LIMIT_DEFAULT,
) -> SearchResponse:
    """JSON search API endpoint."""
    settings: Settings = get_settings()
    limit = min(limit, SEARCH_RESULT_LIMIT_MAX)
    offset = (page - 1) * limit
    year_int: int | None = int(year) if year else None

    result = await asyncio.to_thread(
        _search_sync,
        settings.get_db_path(), q, tkdn_min, validity_only, kbli or None, year_int, limit, offset,
    )

    today = date.today()
    cert_rows = [CertificateRow.from_row(r, today) for r in result["results"]]

    return SearchResponse(
        results=cert_rows,
        total=result["total"],
        query_time_ms=result["query_time_ms"],
        page=page,
        limit=limit,
    )


@router.post("/enrich-tipe", response_class=HTMLResponse)
async def enrich_tipe_from_search(
    request: Request,
    q: str = Form(""),
    tkdn_min: float = Form(0.0),
    kbli: str | None = Form(None),
    year: str | None = Form(None),
) -> HTMLResponse:
    """Enrich Tipe and import missing P3DN products for companies in current search results.

    1. Scrapes tkdn.kemenperin.go.id per company to backfill Tipe.
    2. Scrapes p3dn.kemenperin.go.id per company to import missing products and
       update p3dn_search_last_seen on existing rows.
    """
    from html import escape

    from ..config import get_settings
    from ..db import get_connection
    from ..p3dn_search_scraper import scrape_and_import_p3dn
    from ..search import search as do_search
    from ..tipe_enricher import enrich_tipe_in_db, scrape_tipe_for_company

    settings = get_settings()
    query = q.strip()
    if not query:
        return HTMLResponse(
            '<span class="text-xs text-red-500">Ketik kata kunci pencarian terlebih dahulu.</span>'
        )

    year_int: int | None = int(year) if year else None
    conn = get_connection(settings.get_db_path())
    try:
        # Re-run DB search to get distinct company names from current results
        result = await asyncio.to_thread(
            _search_sync,
            settings.get_db_path(), query, tkdn_min, False, kbli or None, year_int,
            SEARCH_RESULT_LIMIT_DEFAULT, 0,
        )
        companies: list[str] = list(
            dict.fromkeys(
                r["nama_perusahaan"]
                for r in result["results"]
                if r.get("nama_perusahaan")
            )
        )

        if not companies:
            return HTMLResponse(
                '<span class="text-xs text-gray-400">Tidak ada hasil untuk di-enrich.</span>'
            )

        today = date.today()
        tipe_total = {"updated": 0, "inserted": 0, "skipped": 0}
        p3dn_total = {"updated": 0, "inserted": 0, "skipped": 0}
        tipe_failed = 0
        p3dn_failed = 0

        for company in companies:
            # 1. Tipe enrichment from tkdn.kemenperin.go.id
            try:
                scraped = await scrape_tipe_for_company(
                    company, verify_ssl=settings.p3dn.verify_ssl
                )
                stats = enrich_tipe_in_db(conn, company, scraped)
                tipe_total["updated"] += stats["updated"]
                tipe_total["inserted"] += stats["inserted"]
                tipe_total["skipped"] += stats.get("skipped", 0)
            except Exception as exc:
                tipe_failed += 1
                logger.warning("Enrich Tipe failed for %r: %s", company, exc)

            # 2. P3DN product import from p3dn.kemenperin.go.id
            try:
                stats = await scrape_and_import_p3dn(
                    conn, company, today, verify_ssl=settings.p3dn.verify_ssl
                )
                p3dn_total["updated"] += stats["updated"]
                p3dn_total["inserted"] += stats["inserted"]
                p3dn_total["skipped"] += stats.get("skipped", 0)
            except Exception as exc:
                p3dn_failed += 1
                logger.warning("P3DN import failed for %r: %s", company, exc)

    except Exception as exc:
        logger.exception("Tipe enrichment from search failed: %s", exc)
        return HTMLResponse(
            f'<span class="text-xs text-red-500">Error: {escape(str(exc))}</span>'
        )
    finally:
        conn.close()

    parts = []
    if tipe_total["updated"] or tipe_total["inserted"]:
        parts.append(
            f'Tipe: {tipe_total["updated"]} diperbarui, {tipe_total["inserted"]} baru'
        )
    if p3dn_total["inserted"]:
        parts.append(f'P3DN: {p3dn_total["inserted"]} produk baru diimpor')
    if p3dn_total["updated"] and not p3dn_total["inserted"]:
        parts.append(f'P3DN: {p3dn_total["updated"]} baris dicek')
    skipped_total = tipe_total["skipped"] + p3dn_total["skipped"]
    if skipped_total:
        parts.append(f'{skipped_total} baris dilewati')
    if tipe_failed or p3dn_failed:
        parts.append(f'{tipe_failed + p3dn_failed} perusahaan gagal di-scrape')
    summary = " | ".join(parts) if parts else "Tidak ada perubahan"
    text_color = "text-amber-600" if (tipe_failed or p3dn_failed) else "text-green-700"

    return HTMLResponse(
        f'<span class="text-xs {text_color}">'
        f'{summary} ({len(companies)} perusahaan). Refresh hasil untuk melihat perubahan.'
        f'</span>'
    )
