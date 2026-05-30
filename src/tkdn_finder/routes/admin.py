# src/tkdn_finder/routes/admin.py
"""Admin routes: status, manual refresh trigger, synonym management."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
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
        request,
        "admin.html",
        {
            "stats": stats,
            "download_runs": runs,
            "synonyms": synonyms,
        },
    )


_background_tasks: set[asyncio.Task] = set()  # keep strong refs to prevent GC cancellation


def _progress_html(polling: bool = True) -> str:
    """Render progress bar HTML. polling=True adds hx-trigger so HTMX keeps polling."""
    from .. import refresh_state as rs
    state = rs.get_state()

    poll_attrs = (
        'hx-get="/admin/refresh/progress" '
        'hx-trigger="every 1s" '
        'hx-target="#refresh-status" '
        'hx-swap="outerHTML"'
    ) if polling else ""

    if state.error:
        return (
            f'<div id="refresh-status" class="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-sm">'
            f'<p class="font-medium text-red-800">Error</p>'
            f'<p class="mt-1 text-red-700">{state.error}</p>'
            f'</div>'
        )

    if not state.running and state.percent == 100:
        dur = ""
        if state.started_at and state.finished_at:
            secs = int((state.finished_at - state.started_at).total_seconds())
            dur = f" ({secs} detik)"
        return (
            f'<div id="refresh-status" class="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg text-sm"'
            f' hx-get="/admin"'
            f' hx-trigger="load"'
            f' hx-select="#download-runs-section"'
            f' hx-target="#download-runs-section"'
            f' hx-swap="outerHTML">'
            f'<p class="font-medium text-green-800">Selesai{dur}</p>'
            f'<p class="mt-1 text-green-700">'
            f'{state.rows_ingested:,} baris diproses dari {state.years_done} tahun.'
            f'</p>'
            f'</div>'
        )

    bar_color = "bg-blue-600"
    pct = max(state.percent, 5)
    return (
        f'<div id="refresh-status" class="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg" {poll_attrs}>'
        f'<div class="flex items-center justify-between mb-2">'
        f'<span class="text-sm font-medium text-blue-800">{state.stage or "Memulai..."}</span>'
        f'<span class="text-xs text-blue-600 tabular-nums">{pct}%</span>'
        f'</div>'
        f'<div class="w-full bg-blue-200 rounded-full h-1.5">'
        f'<div class="{bar_color} h-1.5 rounded-full transition-all duration-500" style="width:{pct}%"></div>'
        f'</div>'
        f'</div>'
    )


@router.post("/refresh", response_class=HTMLResponse)
async def trigger_refresh(request: Request) -> HTMLResponse:
    """Manually trigger the refresh_all_years job; returns progress HTML for HTMX."""
    from .. import refresh_state as rs
    from ..scheduler import refresh_all_years

    settings = get_settings()

    if rs.get_state().running:
        return HTMLResponse(_progress_html(polling=True))

    task = asyncio.create_task(refresh_all_years(settings, settings.get_db_path()))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    logger.info("Manual refresh triggered via admin")
    return HTMLResponse(_progress_html(polling=True))


@router.get("/refresh/progress", response_class=HTMLResponse)
async def refresh_progress() -> HTMLResponse:
    """Return current refresh progress HTML for HTMX polling."""
    from .. import refresh_state as rs
    state = rs.get_state()
    # Terminal = success (percent==100, not running) or error
    terminal = (not state.running and state.percent == 100) or state.error is not None
    return HTMLResponse(_progress_html(polling=not terminal))



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
) -> HTMLResponse:
    """Add or update a synonym entry; returns updated synonym list partial for HTMX."""
    templates: Jinja2Templates = request.app.state.templates
    settings = get_settings()

    variants_stripped = variants.strip()
    if variants_stripped.startswith("["):
        try:
            json.loads(variants_stripped)
            variants_json = variants_stripped
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON for variants")
    else:
        parts = [v.strip() for v in variants_stripped.split(",") if v.strip()]
        variants_json = json.dumps(parts, ensure_ascii=False)

    conn = get_connection(settings.get_db_path())
    try:
        upsert_synonym(conn, canonical.strip().lower(), variants_json)
        synonyms = get_synonyms_all(conn)
    finally:
        conn.close()

    from ..search import invalidate_synonym_cache
    invalidate_synonym_cache()

    return templates.TemplateResponse(request, "partials/synonym_list.html", {"synonyms": synonyms})


@router.post("/synonym/delete/{synonym_id}")
async def remove_synonym(synonym_id: int, request: Request) -> HTMLResponse:
    """Delete a synonym by ID; returns updated list partial for HTMX."""
    templates: Jinja2Templates = request.app.state.templates
    settings = get_settings()
    conn = get_connection(settings.get_db_path())
    try:
        delete_synonym(conn, synonym_id)
        synonyms = get_synonyms_all(conn)
    finally:
        conn.close()

    from ..search import invalidate_synonym_cache
    invalidate_synonym_cache()

    return templates.TemplateResponse(request, "partials/synonym_list.html", {"synonyms": synonyms})
