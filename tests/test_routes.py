# tests/test_routes.py
"""Integration tests for FastAPI routes."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tkdn_finder.merger import merge_and_upsert
from tkdn_finder.synonyms import seed_default_synonyms


SAMPLE_ROWS = [
    {
        "nama_perusahaan": "PT Test Pompa",
        "nama_produk": "Pompa Sentrifugal",
        "spesifikasi": "Head 30m, Q 50 m3/h",
        "merek": "TestPump",
        "tipe": "TP-50",
        "nilai_tkdn": 40.0,
        "kode_hs": "84137090",
        "kbli": "28131",
        "kelompok_barang": "Pompa",
        "alamat": "Jakarta",
        "provinsi": "DKI Jakarta",
        "masa_berlaku_akhir": "2030-06-30",
        "tahun_sumber": 2026,
    },
    {
        "nama_perusahaan": "PT Kabel Test",
        "nama_produk": "Kabel Daya",
        "spesifikasi": "3x50mm2, 20kV",
        "merek": "TestKabel",
        "tipe": "TK-50",
        "nilai_tkdn": 60.0,
        "kode_hs": "85444200",
        "kbli": "27320",
        "kelompok_barang": "Kabel",
        "alamat": "Surabaya",
        "provinsi": "Jawa Timur",
        "masa_berlaku_akhir": "2031-12-31",
        "tahun_sumber": 2025,
    },
]


@pytest.fixture()
def client(tmp_path: Path):
    """Create a test client with an isolated DB."""
    db_path = str(tmp_path / "test.db")

    from tkdn_finder.db import get_connection, init_db

    init_db(db_path)
    conn = get_connection(db_path)
    merge_and_upsert(conn, SAMPLE_ROWS)
    seed_default_synonyms(conn)
    conn.close()

    from tkdn_finder.main import create_app

    with patch("tkdn_finder.config.Settings.get_db_path", return_value=db_path):
        with patch("tkdn_finder.routes.search.get_settings") as mock_settings, \
             patch("tkdn_finder.routes.health.get_settings") as mock_health_settings, \
             patch("tkdn_finder.routes.admin.get_settings") as mock_admin_settings, \
             patch("tkdn_finder.routes.detail.get_settings") as mock_detail_settings, \
             patch("tkdn_finder.routes.export.get_settings") as mock_export_settings:

            class FakeSettings:
                def get_db_path(self):
                    return db_path
                log_level = "WARNING"
                host = "127.0.0.1"
                port = 8000

            fake = FakeSettings()
            mock_settings.return_value = fake
            mock_health_settings.return_value = fake
            mock_admin_settings.return_value = fake
            mock_detail_settings.return_value = fake
            mock_export_settings.return_value = fake

            app = create_app()

            # Bypass scheduler startup for tests
            app.router.on_startup.clear()

            with TestClient(app) as c:
                yield c


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")


def test_metrics_endpoint(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "tkdn_certificate_total" in resp.text


def test_api_search_empty_query(client: TestClient) -> None:
    resp = client.get("/api/search")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total" in data
    assert data["total"] == len(SAMPLE_ROWS)


def test_api_search_with_query(client: TestClient) -> None:
    resp = client.get("/api/search?q=pompa")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any("Pompa" in r["nama_produk"] for r in data["results"])


def test_api_search_tkdn_min_filter(client: TestClient) -> None:
    resp = client.get("/api/search?tkdn_min=55")
    assert resp.status_code == 200
    data = resp.json()
    for row in data["results"]:
        assert (row["nilai_tkdn"] or 0) >= 55.0


def test_api_search_pagination(client: TestClient) -> None:
    resp = client.get("/api/search?limit=1&page=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 1


def test_cert_detail_not_found(client: TestClient) -> None:
    resp = client.get("/cert/999999")
    assert resp.status_code == 404
