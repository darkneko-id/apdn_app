# src/tkdn_finder/parser.py
"""Parse P3DN HTML table exports (files disguised as .xls)."""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from bs4 import BeautifulSoup

from .constants import (
    DATE_FORMAT,
    HTML_COLUMN_MAP,
    REQUIRED_FIELDS,
    TKDN_SENTINEL_VALUE,
)

logger = logging.getLogger(__name__)

_EMPTY_VALUES = frozenset({"", "-", "−", "–", "—", "N/A", "n/a"})
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_text(value: str | None) -> str | None:
    """Collapse whitespace and return None for empty/dash values."""
    if value is None:
        return None
    cleaned = _WHITESPACE_RE.sub(" ", value).strip()
    if cleaned in _EMPTY_VALUES:
        return None
    return cleaned or None


def _parse_tkdn(value: str | None) -> float | None:
    """Parse TKDN percentage string to float. Returns None on failure."""
    if not value:
        return None
    cleaned = value.strip().replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        logger.warning("Could not parse TKDN value: %r", value)
        return None


def _parse_date(value: str | None) -> str | None:
    """Parse date string; returns ISO date string or None."""
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned or cleaned in _EMPTY_VALUES:
        return None
    try:
        parsed = date.fromisoformat(cleaned)
        return parsed.isoformat()
    except ValueError:
        # Try common date formats
        from datetime import datetime

        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(cleaned, fmt).date()
                return parsed.isoformat()
            except ValueError:
                continue
    logger.error("Could not parse date: %r", value)
    return None


def _extract_headers(header_row: Any) -> list[str]:
    """Extract column header text from a <tr> element."""
    headers = []
    for cell in header_row.find_all(["th", "td"]):
        text = cell.get_text(strip=True)
        headers.append(text)
    return headers


def _map_headers(headers: list[str]) -> dict[int, str]:
    """Map column indices to internal field names using HTML_COLUMN_MAP.

    Logs warnings for unknown headers and returns mapping of known columns only.
    """
    mapping: dict[int, str] = {}
    for idx, header in enumerate(headers):
        internal = HTML_COLUMN_MAP.get(header)
        if internal:
            mapping[idx] = internal
        else:
            logger.warning("Unknown column header at index %d: %r", idx, header)
    return mapping


def parse_html_export(file_path: str, year: str) -> list[dict[str, Any]]:
    """Parse a P3DN HTML table export file.

    Args:
        file_path: Path to the HTML file (may have .xls extension).
        year: Source year string (e.g. "2026").

    Returns:
        List of normalized row dicts ready for DB insertion.
    """
    logger.info("Parsing HTML export: file=%s year=%s", file_path, year)

    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            raw_html = f.read()
    except OSError as exc:
        logger.exception("Cannot open file %s", file_path, extra={"error": str(exc)})
        raise

    soup = BeautifulSoup(raw_html, "lxml")
    table = soup.find("table")
    if not table:
        logger.warning("No <table> found in %s", file_path)
        return []

    rows = table.find_all("tr")
    if not rows:
        logger.warning("Empty table in %s", file_path)
        return []

    # First row is the header
    header_row = rows[0]
    headers = _extract_headers(header_row)
    col_map = _map_headers(headers)

    if not col_map:
        logger.error("No recognized columns in %s; got headers: %r", file_path, headers)
        return []

    today = date.today()
    results: list[dict[str, Any]] = []
    skipped = 0

    for row_idx, tr in enumerate(rows[1:], start=2):
        cells = tr.find_all("td")
        if not cells:
            continue  # Skip header or empty rows

        row_data: dict[str, Any] = {}
        for col_idx, field_name in col_map.items():
            raw_value = cells[col_idx].get_text(strip=False) if col_idx < len(cells) else ""
            row_data[field_name] = raw_value

        # Normalize all text fields
        for field in (
            "nama_perusahaan",
            "nama_produk",
            "spesifikasi",
            "merek",
            "tipe",
            "kode_hs",
            "kbli",
            "kelompok_barang",
            "alamat",
            "provinsi",
        ):
            row_data[field] = _normalize_text(row_data.get(field))

        # Check required fields
        missing = [f for f in REQUIRED_FIELDS if not row_data.get(f)]
        if missing:
            logger.warning(
                "Skipping row %d in %s: missing required fields %r",
                row_idx,
                file_path,
                missing,
                extra={"row_preview": {f: row_data.get(f) for f in REQUIRED_FIELDS}},
            )
            skipped += 1
            continue

        # Parse typed fields
        row_data["nilai_tkdn"] = _parse_tkdn(row_data.get("nilai_tkdn"))
        # Clamp sentinel value
        if row_data["nilai_tkdn"] == TKDN_SENTINEL_VALUE:
            row_data["nilai_tkdn"] = None

        masa_str = _parse_date(row_data.get("masa_berlaku_akhir"))
        row_data["masa_berlaku_akhir"] = masa_str

        try:
            tahun = int(year)
        except ValueError:
            tahun = None
        row_data["tahun_sumber"] = tahun

        results.append(row_data)

    logger.info(
        "Parse complete: file=%s year=%s parsed=%d skipped=%d",
        file_path,
        year,
        len(results),
        skipped,
    )
    return results
