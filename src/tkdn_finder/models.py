# src/tkdn_finder/models.py
"""Pydantic models for API responses and internal data transfer."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, field_validator


class CertificateRow(BaseModel):
    """Represents one TKDN certificate record."""

    id: int
    nama_perusahaan: str
    nama_produk: str
    spesifikasi: str
    merek: str | None = None
    tipe: str | None = None
    nilai_tkdn: float | None = None
    kode_hs: str | None = None
    kbli: str | None = None
    kelompok_barang: str | None = None
    alamat: str | None = None
    provinsi: str | None = None
    masa_berlaku_akhir: date | None = None
    tahun_sumber: int | None = None
    p3dn_search_last_seen: date | None = None
    p3dn_not_found_since: date | None = None
    is_valid: bool = False
    score: float | None = None

    @classmethod
    def from_row(cls, row: object, today: date | None = None) -> "CertificateRow":
        """Construct from sqlite3.Row object."""
        import sqlite3

        if today is None:
            today = date.today()

        d = dict(row)  # type: ignore[call-overload]

        # Compute is_valid
        masa = d.get("masa_berlaku_akhir")
        if isinstance(masa, str) and masa:
            try:
                masa_date = date.fromisoformat(masa)
                d["masa_berlaku_akhir"] = masa_date
                d["is_valid"] = masa_date >= today
            except ValueError:
                d["masa_berlaku_akhir"] = None
                d["is_valid"] = False
        elif isinstance(masa, date):
            d["is_valid"] = masa >= today
        else:
            d["is_valid"] = False

        # Parse date-string columns
        for date_col in ("p3dn_search_last_seen", "p3dn_not_found_since"):
            val = d.get(date_col)
            if isinstance(val, str) and val:
                try:
                    d[date_col] = date.fromisoformat(val)
                except ValueError:
                    d[date_col] = None

        # Remove score from DB dict (it may be added separately)
        d.setdefault("score", None)
        return cls(**d)


def compute_validity_label(cert: CertificateRow, today: date) -> str:
    """Return a display label string combining expiry date and P3DN web presence.

    Labels: 'expired_on_web' | 'not_valid' | 'web_lost' | 'web_active' | 'valid' | 'unknown'

    The two signals — masa_berlaku_akhir (expiry date) and P3DN search.php
    presence (p3dn_search_last_seen / p3dn_not_found_since) — are independent
    and combined rather than treated as mutually exclusive: a certificate can
    have a future expiry date yet no longer appear in P3DN search results
    (label 'web_lost'), or be past its expiry date yet still appear there
    (label 'expired_on_web', surfaced for manual verification rather than
    silently trusting either signal).
    """
    present = cert.p3dn_not_found_since is None and cert.p3dn_search_last_seen is not None

    if cert.masa_berlaku_akhir is not None and cert.masa_berlaku_akhir < today:
        return "expired_on_web" if present else "not_valid"

    # p3dn_not_found_since is the authoritative absence flag (cleared on the
    # scrape that finds the record again), so check it before p3dn_search_last_seen.
    if cert.p3dn_not_found_since is not None:
        if cert.masa_berlaku_akhir is not None and cert.masa_berlaku_akhir >= today:
            return "web_lost"
        return "not_valid"

    if cert.p3dn_search_last_seen is not None:
        return "web_active"

    if cert.masa_berlaku_akhir is not None and cert.masa_berlaku_akhir >= today:
        return "valid"

    return "unknown"


class SearchResponse(BaseModel):
    """Paginated search response."""

    results: list[CertificateRow]
    total: int
    query_time_ms: float
    page: int = 1
    limit: int = 50


class DownloadRunRow(BaseModel):
    """Represents one download run record."""

    id: int
    year_label: str | None = None
    source_url: str | None = None
    status: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    row_count: int | None = None
    error_message: str | None = None
    inserted_count: int | None = None
    updated_count: int | None = None
    skipped_count: int | None = None

    @classmethod
    def from_row(cls, row: object) -> "DownloadRunRow":
        """Construct from sqlite3.Row."""
        d = dict(row)  # type: ignore[call-overload]
        for field in ("started_at", "finished_at"):
            if isinstance(d.get(field), str) and d[field]:
                try:
                    d[field] = datetime.fromisoformat(d[field])
                except ValueError:
                    d[field] = None
        return cls(**d)


class StatsResponse(BaseModel):
    """Admin statistics."""

    total_rows: int
    last_refresh: str | None = None
    rows_per_year: dict[str, int] = {}


class YearTrendChart(BaseModel):
    """Precomputed SVG sparkline data for one year's certificate-count trend.

    Points are spaced evenly by index (not by actual elapsed days) — this is
    a small-multiples trend sparkline, not a precise time-scale axis.
    """

    tahun: int
    current: int
    delta: int | None = None
    min_count: int
    max_count: int
    point_count: int
    polyline: str = ""
    last_x: float
    last_y: float
    width: int
    height: int
    first_date: str | None = None
    last_date: str | None = None
