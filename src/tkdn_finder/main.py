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
from .routes import admin, detail, export, health, search
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
        version="0.1.0",
    )

    # --- Templates ---
    app.state.templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

    # --- Static files (if directory exists) ---
    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # --- Routers ---
    app.include_router(search.router)
    app.include_router(detail.router)
    app.include_router(export.router)
    app.include_router(admin.router, prefix="/admin")
    app.include_router(health.router)

    # --- Startup / shutdown lifecycle ---
    @app.on_event("startup")
    async def startup() -> None:
        db_path = settings.get_db_path()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        init_db(db_path)

        conn = get_connection(db_path)
        try:
            seed_default_synonyms(conn)
        finally:
            conn.close()

        # Start scheduler
        scheduler = create_scheduler(settings, db_path)
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("Application started. DB: %s", db_path)

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
