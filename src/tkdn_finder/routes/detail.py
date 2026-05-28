# src/tkdn_finder/routes/detail.py
"""Certificate detail route."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..config import get_settings
from ..constants import VALIDITY_EXPIRING_SOON_DAYS
from ..db import get_certificate_by_id, get_connection
from ..models import CertificateRow

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/cert/{cert_id}", response_class=HTMLResponse)
async def cert_detail(cert_id: int, request: Request) -> HTMLResponse:
    """Render the certificate detail page."""
    templates: Jinja2Templates = request.app.state.templates
    settings = get_settings()

    conn = get_connection(settings.get_db_path())
    try:
        row = get_certificate_by_id(conn, cert_id)
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Certificate {cert_id} not found")

    today = date.today()
    cert = CertificateRow.from_row(row, today)

    if cert.masa_berlaku_akhir is None:
        validity_label = "unknown"
    elif cert.masa_berlaku_akhir < today:
        validity_label = "expired"
    elif (cert.masa_berlaku_akhir - today).days <= VALIDITY_EXPIRING_SOON_DAYS:
        validity_label = "expiring"
    else:
        validity_label = "valid"

    return templates.TemplateResponse(
        request,
        "detail.html",
        {
            "cert": cert,
            "validity_label": validity_label,
            "today": today,
        },
    )
