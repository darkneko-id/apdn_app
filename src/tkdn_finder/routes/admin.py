# src/tkdn_finder/routes/admin.py
"""Admin routes: status, manual refresh trigger, synonym management."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import get_settings
from ..db import (
    delete_synonym,
    get_connection,
    get_download_runs,
    get_stats,
    get_synonyms_all,
    upsert_synonym,
)
from ..models import DownloadRunRow, StatsResponse
from ..synonyms import load_synonyms

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_page(request: Request) -> HTMLResponse:
    """Render the admin dashboard."""
    templates: Jinja2Templates = request.app.state.templates
    settings = get_settings()

    conn = get_connection(settings.get_db_path())
    try:
        stats = get_stats(conn)
        runs_raw = get_download_runs(conn, limit=10)
        runs = [DownloadRunRow.from_row(r) for r in runs_raw]
        synonyms = get_synonyms_all(conn)
    finally:
        conn.close()

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "stats": stats,
            "runs": runs,
            "synonyms": synonyms,
        },
    )


@router.post("/refresh")
async def trigger_refresh(request: Request) -> dict[str, str]:
    """Manually trigger the refresh_all_years job."""
    from ..scheduler import refresh_all_years

    settings = get_settings()

    import asyncio

    asyncio.create_task(refresh_all_years(settings, settings.get_db_path()))
    logger.info("Manual refresh triggered via admin")
    return {"status": "triggered", "message": "Refresh job queued"}


@router.get("/api/status")
async def admin_status() -> StatsResponse:
    """Return current DB stats as JSON."""
    settings = get_settings()
    conn = get_connection(settings.get_db_path())
    try:
        stats = get_stats(conn)
    finally:
        conn.close()
    return StatsResponse(**stats)


@router.post("/synonym/add")
async def add_synonym(
    request: Request,
    canonical: str = Form(...),
    variants: str = Form(...),
) -> RedirectResponse:
    """Add or update a synonym entry."""
    settings = get_settings()
    # Validate variants as JSON array or comma-separated
    variants_stripped = variants.strip()
    if variants_stripped.startswith("["):
        try:
            json.loads(variants_stripped)
            variants_json = variants_stripped
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON for variants")
    else:
        # Comma-separated
        parts = [v.strip() for v in variants_stripped.split(",") if v.strip()]
        variants_json = json.dumps(parts, ensure_ascii=False)

    conn = get_connection(settings.get_db_path())
    try:
        upsert_synonym(conn, canonical.strip().lower(), variants_json)
    finally:
        conn.close()

    return RedirectResponse(url="/admin", status_code=303)


@router.post("/synonym/delete/{synonym_id}")
async def remove_synonym(synonym_id: int, request: Request) -> RedirectResponse:
    """Delete a synonym by ID."""
    settings = get_settings()
    conn = get_connection(settings.get_db_path())
    try:
        delete_synonym(conn, synonym_id)
    finally:
        conn.close()
    return RedirectResponse(url="/admin", status_code=303)
