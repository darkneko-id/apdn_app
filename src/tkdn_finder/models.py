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


def compute_validity_label(cert: CertificateRow, today: date, expiring_soon_days: int = 60) -> str:
    """Return a display label string for a certificate's validity status.

    Labels: 'valid' | 'expiring' | 'expired' | 'p3dn_active' | 'p3dn_not_found' | 'unknown'
    """
    if cert.masa_berlaku_akhir is not None:
        if cert.masa_berlaku_akhir < today:
            return "expired"
        if (cert.masa_berlaku_akhir - today).days <= expiring_soon_days:
            return "expiring"
        return "valid"
    # No masa_berlaku_akhir — check P3DN tracking
    if cert.p3dn_search_last_seen is not None:
        return "p3dn_active" if cert.p3dn_search_last_seen >= today else "p3dn_not_found"
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
