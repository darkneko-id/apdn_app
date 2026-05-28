# src/tkdn_finder/routes/search.py
"""Search routes: GET / (HTML), GET /search (HTMX partial), GET /api/search (JSON)."""

from __future__ import annotations

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
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
from ..db import get_connection, get_kbli_list, get_year_list
from ..models import CertificateRow, SearchResponse
from ..search import search as do_search

logger = logging.getLogger(__name__)
router = APIRouter()


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
    finally:
        conn.close()

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "kbli_list": kbli_list,
            "year_list": year_list,
            "debounce_ms": SEARCH_DEBOUNCE_MS,
        },
    )


@router.get("/search", response_class=HTMLResponse)
async def search_htmx(
    request: Request,
    q: str = "",
    tkdn_min: float = TKDN_DEFAULT_MIN_FILTER,
    validity_only: bool = False,
    kbli: str | None = None,
    year: int | None = None,
    page: int = 1,
    limit: int = SEARCH_RESULT_LIMIT_DEFAULT,
) -> HTMLResponse:
    """HTMX search endpoint — returns results.html partial."""
    templates: Jinja2Templates = request.app.state.templates
    settings: Settings = get_settings()
    limit = min(limit, SEARCH_RESULT_LIMIT_MAX)
    offset = (page - 1) * limit

    conn = get_connection(settings.get_db_path())
    try:
        result = do_search(
            conn=conn,
            query=q,
            tkdn_min=tkdn_min,
            validity_only=validity_only,
            kbli=kbli or None,
            year=year,
            limit=limit,
            offset=offset,
        )
    finally:
        conn.close()

    today = date.today()
    cert_rows = [CertificateRow.from_row(r, today) for r in result["results"]]

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
            "year": year,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
        },
    )


@router.get("/api/search")
async def search_api(
    q: str = "",
    tkdn_min: float = TKDN_DEFAULT_MIN_FILTER,
    validity_only: bool = False,
    kbli: str | None = None,
    year: int | None = None,
    page: int = 1,
    limit: int = SEARCH_RESULT_LIMIT_DEFAULT,
) -> SearchResponse:
    """JSON search API endpoint."""
    settings: Settings = get_settings()
    limit = min(limit, SEARCH_RESULT_LIMIT_MAX)
    offset = (page - 1) * limit

    conn = get_connection(settings.get_db_path())
    try:
        result = do_search(
            conn=conn,
            query=q,
            tkdn_min=tkdn_min,
            validity_only=validity_only,
            kbli=kbli or None,
            year=year,
            limit=limit,
            offset=offset,
        )
    finally:
        conn.close()

    today = date.today()
    cert_rows = [CertificateRow.from_row(r, today) for r in result["results"]]

    return SearchResponse(
        results=cert_rows,
        total=result["total"],
        query_time_ms=result["query_time_ms"],
        page=page,
        limit=limit,
    )
