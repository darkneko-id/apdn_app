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
    VALIDITY_EXPIRING_SOON_DAYS,
)
from ..db import get_connection, get_kbli_list, get_last_refresh_ts, get_year_list
from ..models import CertificateRow, SearchResponse
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
    tagged_rows = []
    for cert in cert_rows:
        if cert.masa_berlaku_akhir is None:
            validity_label = "unknown"
        elif cert.masa_berlaku_akhir < today:
            validity_label = "expired"
        elif (cert.masa_berlaku_akhir - today).days <= VALIDITY_EXPIRING_SOON_DAYS:
            validity_label = "expiring"
        else:
            validity_label = "valid"
        tagged_rows.append((cert, validity_label))

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
    """Enrich Tipe for all companies visible in the current search results.

    Strategy: re-run the DB search to get distinct company names from the
    current result page, then scrape tkdn.kemenperin.go.id per company.
    Works for both single-company and multi-company result sets.
    """
    from html import escape

    from ..config import get_settings
    from ..db import get_connection
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

        total = {"updated": 0, "inserted": 0, "skipped": 0}
        for company in companies:
            try:
                scraped = await scrape_tipe_for_company(
                    company, verify_ssl=settings.p3dn.verify_ssl
                )
                stats = enrich_tipe_in_db(conn, company, scraped)
                total["updated"] += stats["updated"]
                total["inserted"] += stats["inserted"]
                total["skipped"] += stats["skipped"]
            except Exception as exc:
                logger.warning("Enrich Tipe failed for %r: %s", company, exc)

    except Exception as exc:
        logger.exception("Tipe enrichment from search failed: %s", exc)
        return HTMLResponse(
            f'<span class="text-xs text-red-500">Error: {escape(str(exc))}</span>'
        )
    finally:
        conn.close()

    return HTMLResponse(
        f'<span class="text-xs text-green-700">'
        f'Tipe diperbarui: {total["updated"]} baris, {total["inserted"]} baru '
        f'({len(companies)} perusahaan). Refresh hasil untuk melihat perubahan.'
        f'</span>'
    )
