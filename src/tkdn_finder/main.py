# src/tkdn_finder/main.py
"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .db import get_connection, init_db
from .routes import admin, bantuan, detail, export, health, search
from .scheduler import create_scheduler
from .synonyms import seed_default_synonyms

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(
        title="TKDN Finder",
        description="Pencarian sertifikat TKDN dari Kemenperin P3DN",
        version="1.0.0",
    )

    # --- Templates ---
    app.state.templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

    def _to_wib(value: object) -> str:
        """Convert a UTC datetime string or object to WIB (UTC+7) display string."""
        from datetime import datetime, timedelta, timezone
        WIB = timezone(timedelta(hours=7))
        if value is None:
            return "—"
        if isinstance(value, datetime):
            dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        elif isinstance(value, str):
            s = value.strip()
            if not s:
                return "—"
            # Normalise space separator → T so fromisoformat handles both forms
            s = s.replace(" ", "T", 1)
            try:
                dt = datetime.fromisoformat(s)
            except ValueError:
                return value[:19].replace("T", " ")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            return str(value)
        return dt.astimezone(WIB).strftime("%d %b %Y %H:%M WIB")

    app.state.templates.env.filters["wib"] = _to_wib

    # --- Static files (if directory exists) ---
    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # --- Routers ---
    app.include_router(search.router)
    app.include_router(detail.router)
    app.include_router(export.router)
    app.include_router(admin.router, prefix="/admin")
    app.include_router(health.router)
    app.include_router(bantuan.router)

    # --- Startup / shutdown lifecycle ---
    @app.on_event("startup")
    async def startup() -> None:
        import asyncio
        from .scheduler import refresh_all_years

        db_path = settings.get_db_path()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        init_db(db_path)

        conn = get_connection(db_path)
        try:
            seed_default_synonyms(conn)
            is_empty = conn.execute("SELECT COUNT(*) FROM tkdn_certificate").fetchone()[0] == 0
        finally:
            conn.close()

        # Start scheduler
        scheduler = create_scheduler(settings, db_path)
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("Application started. DB: %s", db_path)

        # Auto-download on first run (empty DB)
        if is_empty:
            logger.info("DB is empty — triggering initial data download")
            asyncio.create_task(refresh_all_years(settings, db_path))

    @app.on_event("shutdown")
    async def shutdown() -> None:
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        logger.info("Application shutdown")

    return app


app = create_app()


def main() -> None:
    """Entry point for the tkdn-finder CLI command."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "tkdn_finder.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
