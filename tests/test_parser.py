# tests/test_parser.py
"""Tests for tkdn_finder.parser module."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from tkdn_finder.parser import parse_html_export


def _write_html(path: Path, content: str) -> str:
    """Write HTML content to a temp file and return path string."""
    p = path / "test.html"
    p.write_text(content, encoding="utf-8")
    return str(p)


VALID_HTML = textwrap.dedent("""\
    <html><body><table>
    <tr>
      <th>Kode HS</th><th>KBLI</th><th>Kelompok Barang</th>
      <th>Nama Perusahaan</th><th>Alamat</th><th>Provinsi</th>
      <th>Produk</th><th>Spesifikasi</th><th>Tipe</th><th>Merk</th>
      <th>Nilai TKDN (%)</th><th>Tanggal Kadaluarsa Sertifikat</th>
    </tr>
    <tr>
      <td>8413.50</td><td>28132</td><td>Pompa</td>
      <td>PT Contoh</td><td>Jl. Test</td><td>Jawa Barat</td>
      <td>Pompa Air</td><td>Kapasitas 50L/min</td><td>PA-50</td><td>BrandX</td>
      <td>40.00</td><td>2027-12-31</td>
    </tr>
    </table></body></html>
""")

MISSING_REQUIRED_HTML = textwrap.dedent("""\
    <html><body><table>
    <tr>
      <th>Kode HS</th><th>KBLI</th><th>Kelompok Barang</th>
      <th>Nama Perusahaan</th><th>Alamat</th><th>Provinsi</th>
      <th>Produk</th><th>Spesifikasi</th><th>Tipe</th><th>Merk</th>
      <th>Nilai TKDN (%)</th><th>Tanggal Kadaluarsa Sertifikat</th>
    </tr>
    <tr>
      <td>8413.50</td><td>28132</td><td>Pompa</td>
      <td></td><td>Jl. Test</td><td>Jawa Barat</td>
      <td>Pompa Air</td><td>Kapasitas 50L/min</td><td>PA-50</td><td>BrandX</td>
      <td>40.00</td><td>2027-12-31</td>
    </tr>
    </table></body></html>
""")

EXTRA_COLUMN_HTML = textwrap.dedent("""\
    <html><body><table>
    <tr>
      <th>Kode HS</th><th>KBLI</th><th>Kelompok Barang</th>
      <th>Nama Perusahaan</th><th>Alamat</th><th>Provinsi</th>
      <th>Produk</th><th>Spesifikasi</th><th>Tipe</th><th>Merk</th>
      <th>Nilai TKDN (%)</th><th>Tanggal Kadaluarsa Sertifikat</th>
      <th>Kolom Baru Tidak Dikenal</th>
    </tr>
    <tr>
      <td>8413.50</td><td>28132</td><td>Pompa</td>
      <td>PT Extra Col</td><td>Jl. Extra</td><td>Banten</td>
      <td>Produk Extra</td><td>Spec Extra</td><td>T-X</td><td>BrandY</td>
      <td>30.00</td><td>2027-06-30</td>
      <td>nilai kolom baru</td>
    </tr>
    </table></body></html>
""")

MALFORMED_DATE_HTML = textwrap.dedent("""\
    <html><body><table>
    <tr>
      <th>Kode HS</th><th>KBLI</th><th>Kelompok Barang</th>
      <th>Nama Perusahaan</th><th>Alamat</th><th>Provinsi</th>
      <th>Produk</th><th>Spesifikasi</th><th>Tipe</th><th>Merk</th>
      <th>Nilai TKDN (%)</th><th>Tanggal Kadaluarsa Sertifikat</th>
    </tr>
    <tr>
      <td>8413.50</td><td>28132</td><td>Pompa</td>
      <td>PT Bad Date</td><td>Jl. Bad</td><td>Sulawesi</td>
      <td>Produk Tanggal Buruk</td><td>Spesifikasi Normal</td><td>T-B</td><td>BrandZ</td>
      <td>25.00</td><td>bukan-tanggal</td>
    </tr>
    </table></body></html>
""")

EMPTY_TABLE_HTML = textwrap.dedent("""\
    <html><body><table>
    <tr>
      <th>Kode HS</th><th>KBLI</th><th>Kelompok Barang</th>
      <th>Nama Perusahaan</th><th>Alamat</th><th>Provinsi</th>
      <th>Produk</th><th>Spesifikasi</th><th>Tipe</th><th>Merk</th>
      <th>Nilai TKDN (%)</th><th>Tanggal Kadaluarsa Sertifikat</th>
    </tr>
    </table></body></html>
""")

NO_TABLE_HTML = "<html><body><p>Tidak ada tabel</p></body></html>"


class TestParseHtmlExport:
    def test_happy_path(self, tmp_path: Path) -> None:
        """Parser returns correct normalized row for valid input."""
        path = _write_html(tmp_path, VALID_HTML)
        rows = parse_html_export(path, "2027")

        assert len(rows) == 1
        row = rows[0]
        assert row["nama_perusahaan"] == "PT Contoh"
        assert row["nama_produk"] == "Pompa Air"
        assert row["spesifikasi"] == "Kapasitas 50L/min"
        assert row["nilai_tkdn"] == pytest.approx(40.0)
        assert row["masa_berlaku_akhir"] == "2027-12-31"
        assert row["tahun_sumber"] == 2027
        assert row["merek"] == "BrandX"

    def test_missing_required_field_skips_row(self, tmp_path: Path) -> None:
        """Row with missing nama_perusahaan is skipped."""
        path = _write_html(tmp_path, MISSING_REQUIRED_HTML)
        rows = parse_html_export(path, "2027")
        assert rows == []

    def test_extra_unknown_column_does_not_fail(self, tmp_path: Path) -> None:
        """Unknown column header is warned about but does not crash."""
        path = _write_html(tmp_path, EXTRA_COLUMN_HTML)
        rows = parse_html_export(path, "2027")
        assert len(rows) == 1
        assert rows[0]["nama_perusahaan"] == "PT Extra Col"

    def test_malformed_date_returns_none(self, tmp_path: Path) -> None:
        """Row with malformed date gets masa_berlaku_akhir=None, row still included."""
        path = _write_html(tmp_path, MALFORMED_DATE_HTML)
        rows = parse_html_export(path, "2027")
        assert len(rows) == 1
        assert rows[0]["masa_berlaku_akhir"] is None

    def test_empty_table_returns_empty_list(self, tmp_path: Path) -> None:
        """Table with only header row returns empty list."""
        path = _write_html(tmp_path, EMPTY_TABLE_HTML)
        rows = parse_html_export(path, "2027")
        assert rows == []

    def test_no_table_returns_empty_list(self, tmp_path: Path) -> None:
        """HTML without a table returns empty list."""
        path = _write_html(tmp_path, NO_TABLE_HTML)
        rows = parse_html_export(path, "2027")
        assert rows == []

    def test_dash_values_normalized_to_none(self, tmp_path: Path) -> None:
        """Values like '-' in tipe/merek are normalized to None."""
        path = _write_html(tmp_path, VALID_HTML.replace("<td>PA-50</td>", "<td>-</td>"))
        rows = parse_html_export(path, "2027")
        assert len(rows) == 1
        assert rows[0]["tipe"] is None

    def test_fixture_2024(self, sample_2024_path: str) -> None:
        """2024 fixture parses to 3 rows."""
        rows = parse_html_export(sample_2024_path, "2024")
        assert len(rows) == 3

    def test_fixture_2025(self, sample_2025_path: str) -> None:
        """2025 fixture parses to 2 rows."""
        rows = parse_html_export(sample_2025_path, "2025")
        assert len(rows) == 2

    def test_fixture_2026_skips_incomplete_row(self, sample_2026_path: str) -> None:
        """2026 fixture skips the row with missing perusahaan, returning 4 rows."""
        rows = parse_html_export(sample_2026_path, "2026")
        assert len(rows) == 4

    def test_year_set_on_rows(self, sample_2024_path: str) -> None:
        """All rows have the correct tahun_sumber."""
        rows = parse_html_export(sample_2024_path, "2024")
        assert all(r["tahun_sumber"] == 2024 for r in rows)

    def test_duplicate_cert_across_years(self, tmp_path: Path) -> None:
        """Same product parsed from two years yields two separate rows."""
        rows_2024 = parse_html_export(str(tmp_path / ".."), "2024") or []
        # Both fixtures have 'Pompa Sentrifugal' for 'PT Pompa Nusantara'
        from pathlib import Path as P
        rows_2024 = parse_html_export(
            str(P(__file__).parent / "fixtures" / "sample_2024.html"), "2024"
        )
        rows_2025 = parse_html_export(
            str(P(__file__).parent / "fixtures" / "sample_2025.html"), "2025"
        )
        pump_2024 = [r for r in rows_2024 if r["nama_produk"] == "Pompa Sentrifugal"]
        pump_2025 = [r for r in rows_2025 if r["nama_produk"] == "Pompa Sentrifugal"]
        assert len(pump_2024) == 1
        assert len(pump_2025) == 1
        assert pump_2024[0]["tahun_sumber"] == 2024
        assert pump_2025[0]["tahun_sumber"] == 2025
