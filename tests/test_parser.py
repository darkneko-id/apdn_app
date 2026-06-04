"""Tests for parser.py — P3DN HTML export parsing & normalisation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tkdn_finder.parser import _normalize_text, _parse_date, _parse_tkdn, parse_html_export

# ---------------------------------------------------------------------------
# HTML fixture helpers
# ---------------------------------------------------------------------------

_HEADERS = (
    "Kode HS", "KBLI", "Kelompok Barang", "Nama Perusahaan", "Alamat",
    "Provinsi", "Produk", "Spesifikasi", "Tipe", "Merk",
    "Nilai TKDN (%)", "Tanggal Kadaluarsa Sertifikat",
)


def _html_table(*data_rows: tuple[str, ...]) -> str:
    """Wrap header + data rows in a minimal P3DN-style HTML table."""
    header = "<tr>" + "".join(f"<th>{h}</th>" for h in _HEADERS) + "</tr>"
    rows = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in data_rows
    )
    return f"<html><body><table>{header}{rows}</table></body></html>"


def _valid_row(**overrides: str) -> tuple[str, ...]:
    """Return a full row tuple in header order, with optional cell overrides."""
    defaults = {
        "Kode HS": "8413.11",
        "KBLI": "28101",
        "Kelompok Barang": "Pompa",
        "Nama Perusahaan": "PT Maju Jaya",
        "Alamat": "Jl. Industri 1",
        "Provinsi": "DKI Jakarta",
        "Produk": "Centrifugal Pump",
        "Spesifikasi": "6 inch 200 GPM",
        "Tipe": "",
        "Merk": "MJ-100",
        "Nilai TKDN (%)": "40.50",
        "Tanggal Kadaluarsa Sertifikat": "2027-12-31",
    }
    defaults.update(overrides)
    return tuple(defaults[h] for h in _HEADERS)


def _write_html(tmp_path: Path, html: str) -> str:
    f = tmp_path / "export.xls"
    f.write_text(html, encoding="utf-8")
    return str(f)


# ---------------------------------------------------------------------------
# _normalize_text
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_none_returns_none(self) -> None:
        assert _normalize_text(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _normalize_text("") is None

    @pytest.mark.parametrize("value", ["-", "−", "–", "—", "N/A", "n/a"])
    def test_empty_sentinel_values_return_none(self, value: str) -> None:
        assert _normalize_text(value) is None

    def test_collapses_internal_whitespace(self) -> None:
        assert _normalize_text("  pump   centrifugal  ") == "pump centrifugal"

    def test_strips_leading_trailing_whitespace(self) -> None:
        assert _normalize_text("  pump  ") == "pump"

    def test_preserves_normal_text(self) -> None:
        assert _normalize_text("PT Maju Jaya") == "PT Maju Jaya"

    def test_whitespace_only_returns_none(self) -> None:
        assert _normalize_text("   ") is None


# ---------------------------------------------------------------------------
# _parse_tkdn
# ---------------------------------------------------------------------------

class TestParseTkdn:
    def test_plain_float_string(self) -> None:
        assert _parse_tkdn("40.50") == pytest.approx(40.50)

    def test_comma_decimal_separator(self) -> None:
        assert _parse_tkdn("40,50") == pytest.approx(40.50)

    def test_excel_time_format_hhmmss(self) -> None:
        # "37.01.00" means 37 hours 01 min → 37.01%
        assert _parse_tkdn("37.01.00") == pytest.approx(37.01)

    def test_excel_time_format_zero_minutes(self) -> None:
        assert _parse_tkdn("100.00.00") == pytest.approx(100.0)

    def test_none_returns_none(self) -> None:
        assert _parse_tkdn(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse_tkdn("") is None

    def test_non_numeric_returns_none(self) -> None:
        assert _parse_tkdn("tidak ada") is None

    def test_whitespace_stripped_before_parse(self) -> None:
        assert _parse_tkdn("  55.00  ") == pytest.approx(55.0)


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_iso_format(self) -> None:
        assert _parse_date("2027-12-31") == "2027-12-31"

    def test_dd_mm_yyyy_with_dash(self) -> None:
        assert _parse_date("31-12-2027") == "2027-12-31"

    def test_dd_mm_yyyy_with_slash(self) -> None:
        assert _parse_date("31/12/2027") == "2027-12-31"

    def test_yyyy_mm_dd_with_slash(self) -> None:
        assert _parse_date("2027/12/31") == "2027-12-31"

    def test_none_returns_none(self) -> None:
        assert _parse_date(None) is None

    def test_empty_returns_none(self) -> None:
        assert _parse_date("") is None

    @pytest.mark.parametrize("value", ["-", "—", "N/A"])
    def test_sentinel_values_return_none(self, value: str) -> None:
        assert _parse_date(value) is None

    def test_unparseable_returns_none(self) -> None:
        assert _parse_date("not-a-date") is None

    def test_returns_iso_string_format(self) -> None:
        result = _parse_date("01-06-2026")
        assert result == "2026-06-01"


# ---------------------------------------------------------------------------
# parse_html_export — integration
# ---------------------------------------------------------------------------

class TestParseHtmlExport:
    def test_parses_valid_row(self, tmp_path: Path) -> None:
        html = _html_table(_valid_row())
        path = _write_html(tmp_path, html)

        results = parse_html_export(path, "2025")

        assert len(results) == 1
        row = results[0]
        assert row["nama_perusahaan"] == "PT Maju Jaya"
        assert row["nama_produk"] == "Centrifugal Pump"
        assert row["kbli"] == "28101"
        assert row["nilai_tkdn"] == pytest.approx(40.50)
        assert row["masa_berlaku_akhir"] == "2027-12-31"
        assert row["tahun_sumber"] == 2025

    def test_excel_time_tkdn_parsed_correctly(self, tmp_path: Path) -> None:
        html = _html_table(_valid_row(**{"Nilai TKDN (%)": "37.01.00"}))
        path = _write_html(tmp_path, html)

        results = parse_html_export(path, "2025")

        assert results[0]["nilai_tkdn"] == pytest.approx(37.01)

    def test_sentinel_tkdn_clamped_to_none(self, tmp_path: Path) -> None:
        html = _html_table(_valid_row(**{"Nilai TKDN (%)": "999.99"}))
        path = _write_html(tmp_path, html)

        results = parse_html_export(path, "2025")

        assert results[0]["nilai_tkdn"] is None

    def test_empty_cell_values_normalised_to_none(self, tmp_path: Path) -> None:
        html = _html_table(_valid_row(Merk="-", Tipe="—", **{"Kode HS": "N/A"}))
        path = _write_html(tmp_path, html)

        results = parse_html_export(path, "2025")

        assert results[0]["merek"] is None
        assert results[0]["tipe"] is None
        assert results[0]["kode_hs"] is None

    def test_invalid_kbli_cleared_to_none(self, tmp_path: Path) -> None:
        # KBLI must be exactly 5 digits; "28AB1" is invalid
        html = _html_table(_valid_row(KBLI="28AB1"))
        path = _write_html(tmp_path, html)

        results = parse_html_export(path, "2025")

        assert results[0]["kbli"] is None

    def test_kbli_fewer_than_5_digits_cleared(self, tmp_path: Path) -> None:
        html = _html_table(_valid_row(KBLI="2810"))
        path = _write_html(tmp_path, html)

        results = parse_html_export(path, "2025")

        assert results[0]["kbli"] is None

    def test_row_missing_nama_perusahaan_skipped(self, tmp_path: Path) -> None:
        html = _html_table(_valid_row(**{"Nama Perusahaan": ""}))
        path = _write_html(tmp_path, html)

        results = parse_html_export(path, "2025")

        assert results == []

    def test_row_missing_nama_produk_skipped(self, tmp_path: Path) -> None:
        html = _html_table(_valid_row(Produk="-"))
        path = _write_html(tmp_path, html)

        results = parse_html_export(path, "2025")

        assert results == []

    def test_no_table_returns_empty_list(self, tmp_path: Path) -> None:
        path = _write_html(tmp_path, "<html><body><p>No table here</p></body></html>")

        results = parse_html_export(path, "2025")

        assert results == []

    def test_invalid_year_string_yields_none_tahun(self, tmp_path: Path) -> None:
        html = _html_table(_valid_row())
        path = _write_html(tmp_path, html)

        results = parse_html_export(path, "not_a_year")

        assert results[0]["tahun_sumber"] is None

    def test_multiple_rows_all_parsed(self, tmp_path: Path) -> None:
        row1 = _valid_row(**{"Nama Perusahaan": "PT Alpha", "Produk": "Pump A"})
        row2 = _valid_row(**{"Nama Perusahaan": "PT Beta", "Produk": "Pump B"})
        html = _html_table(row1, row2)
        path = _write_html(tmp_path, html)

        results = parse_html_export(path, "2025")

        assert len(results) == 2
        assert results[0]["nama_perusahaan"] == "PT Alpha"
        assert results[1]["nama_perusahaan"] == "PT Beta"

    def test_whitespace_in_cells_normalised(self, tmp_path: Path) -> None:
        html = _html_table(_valid_row(**{"Nama Perusahaan": "  PT   Maju  Jaya  "}))
        path = _write_html(tmp_path, html)

        results = parse_html_export(path, "2025")

        assert results[0]["nama_perusahaan"] == "PT Maju Jaya"

    def test_date_alternative_format_parsed(self, tmp_path: Path) -> None:
        html = _html_table(_valid_row(**{"Tanggal Kadaluarsa Sertifikat": "31-12-2027"}))
        path = _write_html(tmp_path, html)

        results = parse_html_export(path, "2025")

        assert results[0]["masa_berlaku_akhir"] == "2027-12-31"

    def test_unknown_column_header_ignored_gracefully(self, tmp_path: Path) -> None:
        # Add an extra unknown column; should not crash
        html = (
            "<html><body><table>"
            "<tr><th>Nama Perusahaan</th><th>Produk</th><th>KOLOM_BARU</th></tr>"
            "<tr><td>PT Alpha</td><td>Pump</td><td>ignored</td></tr>"
            "</table></body></html>"
        )
        path = _write_html(tmp_path, html)

        results = parse_html_export(path, "2025")

        assert len(results) == 1
        assert results[0]["nama_perusahaan"] == "PT Alpha"
