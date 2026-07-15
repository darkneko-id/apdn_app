"""Tests for year-count trend snapshots (db.py) and sparkline geometry (charts.py)."""

from __future__ import annotations

import sqlite3
from typing import Any

from tkdn_finder.charts import build_year_trend_chart
from tkdn_finder.db import get_year_count_trends, save_year_count_snapshots
from tkdn_finder.merger import merge_and_upsert

# ---------------------------------------------------------------------------
# save_year_count_snapshots
# ---------------------------------------------------------------------------

class TestSaveYearCountSnapshots:
    def test_records_one_row_per_year(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(
            db,
            [
                cert_factory(nama_produk="Pump A", tahun_sumber=2024),
                cert_factory(nama_produk="Pump B", tahun_sumber=2025),
            ],
        )

        save_year_count_snapshots(db, "2026-01-01")

        rows = db.execute(
            "SELECT tahun_sumber, cert_count FROM year_count_snapshot ORDER BY tahun_sumber"
        ).fetchall()
        assert [dict(r) for r in rows] == [
            {"tahun_sumber": 2024, "cert_count": 1},
            {"tahun_sumber": 2025, "cert_count": 1},
        ]

    def test_same_day_rerun_overwrites_not_duplicates(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [cert_factory(tahun_sumber=2025)])
        save_year_count_snapshots(db, "2026-01-01")

        merge_and_upsert(db, [cert_factory(nama_produk="New Pump", tahun_sumber=2025)])
        save_year_count_snapshots(db, "2026-01-01")

        rows = db.execute(
            "SELECT cert_count FROM year_count_snapshot WHERE tahun_sumber = 2025"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["cert_count"] == 2

    def test_different_day_adds_new_point(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [cert_factory(tahun_sumber=2025)])
        save_year_count_snapshots(db, "2026-01-01")
        save_year_count_snapshots(db, "2026-01-02")

        rows = db.execute(
            "SELECT snapshot_date FROM year_count_snapshot WHERE tahun_sumber = 2025 ORDER BY snapshot_date"
        ).fetchall()
        assert [r["snapshot_date"] for r in rows] == ["2026-01-01", "2026-01-02"]

    def test_null_tahun_sumber_excluded(
        self, db: sqlite3.Connection, cert_factory: Any
    ) -> None:
        merge_and_upsert(db, [cert_factory(tahun_sumber=None)])
        save_year_count_snapshots(db, "2026-01-01")

        rows = db.execute("SELECT * FROM year_count_snapshot").fetchall()
        assert rows == []


# ---------------------------------------------------------------------------
# get_year_count_trends
# ---------------------------------------------------------------------------

class TestGetYearCountTrends:
    def test_orders_points_oldest_first_within_year(self, db: sqlite3.Connection) -> None:
        for d, c in [("2026-01-01", 10), ("2026-01-03", 12), ("2026-01-02", 11)]:
            db.execute(
                "INSERT INTO year_count_snapshot (snapshot_date, tahun_sumber, cert_count) VALUES (?, 2025, ?)",
                (d, c),
            )
        db.commit()

        trends = get_year_count_trends(db)

        dates = [r["snapshot_date"] for r in trends[2025]]
        assert dates == ["2026-01-01", "2026-01-02", "2026-01-03"]

    def test_limit_per_year_keeps_most_recent(self, db: sqlite3.Connection) -> None:
        for i in range(5):
            db.execute(
                "INSERT INTO year_count_snapshot (snapshot_date, tahun_sumber, cert_count) VALUES (?, 2025, ?)",
                (f"2026-01-{i + 1:02d}", 10 + i),
            )
        db.commit()

        trends = get_year_count_trends(db, limit_per_year=2)

        dates = [r["snapshot_date"] for r in trends[2025]]
        assert dates == ["2026-01-04", "2026-01-05"]

    def test_years_kept_separate(self, db: sqlite3.Connection) -> None:
        db.execute(
            "INSERT INTO year_count_snapshot (snapshot_date, tahun_sumber, cert_count) VALUES ('2026-01-01', 2024, 5)"
        )
        db.execute(
            "INSERT INTO year_count_snapshot (snapshot_date, tahun_sumber, cert_count) VALUES ('2026-01-01', 2025, 9)"
        )
        db.commit()

        trends = get_year_count_trends(db)

        assert set(trends.keys()) == {2024, 2025}
        assert trends[2024][0]["cert_count"] == 5
        assert trends[2025][0]["cert_count"] == 9

    def test_empty_table_returns_empty_dict(self, db: sqlite3.Connection) -> None:
        assert get_year_count_trends(db) == {}


# ---------------------------------------------------------------------------
# build_year_trend_chart
# ---------------------------------------------------------------------------

def _rows(pairs: list[tuple[str, int]]) -> list[sqlite3.Row]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (snapshot_date TEXT, cert_count INTEGER)")
    conn.executemany("INSERT INTO t VALUES (?, ?)", pairs)
    rows = conn.execute("SELECT * FROM t ORDER BY snapshot_date").fetchall()
    conn.close()
    return rows


class TestBuildYearTrendChart:
    def test_single_point_has_no_polyline(self) -> None:
        chart = build_year_trend_chart(2025, _rows([("2026-01-01", 10)]))

        assert chart.polyline == ""
        assert chart.delta is None
        assert chart.current == 10
        assert chart.point_count == 1

    def test_multi_point_polyline_has_matching_coordinate_count(self) -> None:
        rows = _rows([("2026-01-01", 10), ("2026-01-02", 20), ("2026-01-03", 15)])
        chart = build_year_trend_chart(2025, rows)

        assert len(chart.polyline.split(" ")) == 3
        assert chart.current == 15
        assert chart.delta == -5
        assert chart.min_count == 10
        assert chart.max_count == 20

    def test_flat_line_does_not_divide_by_zero(self) -> None:
        rows = _rows([("2026-01-01", 10), ("2026-01-02", 10)])
        chart = build_year_trend_chart(2025, rows)

        assert chart.min_count == chart.max_count == 10
        assert chart.delta == 0

    def test_last_point_within_svg_bounds(self) -> None:
        rows = _rows([("2026-01-01", 1), ("2026-01-02", 1000)])
        chart = build_year_trend_chart(2025, rows)

        assert 0 <= chart.last_x <= chart.width
        assert 0 <= chart.last_y <= chart.height

    def test_first_and_last_date_recorded(self) -> None:
        rows = _rows([("2026-01-01", 10), ("2026-01-05", 12)])
        chart = build_year_trend_chart(2025, rows)

        assert chart.first_date == "2026-01-01"
        assert chart.last_date == "2026-01-05"


# ---------------------------------------------------------------------------
# Migration 013 backfill from download_run
# ---------------------------------------------------------------------------

class TestMigrationBackfill:
    def test_backfills_snapshot_from_successful_download_run(
        self, db: sqlite3.Connection
    ) -> None:
        db.execute(
            """
            INSERT INTO download_run
                (year_label, source_url, status, started_at, finished_at, row_count)
            VALUES ('2024', 'http://example.test', 'success',
                    '2026-01-01T00:00:00+00:00', '2026-01-01T02:00:00+00:00', 500)
            """
        )
        db.commit()
        # Re-apply migrations (idempotent) to trigger the backfill INSERT again
        # against the freshly-inserted download_run row.
        from tkdn_finder.db import _apply_migrations

        db.execute("DELETE FROM schema_version WHERE version = 13")
        _apply_migrations(db)

        row = db.execute(
            "SELECT cert_count FROM year_count_snapshot WHERE tahun_sumber = 2024 AND snapshot_date = '2026-01-01'"
        ).fetchone()
        assert row is not None
        assert row["cert_count"] == 500

    def test_ignores_failed_runs(self, db: sqlite3.Connection) -> None:
        db.execute(
            """
            INSERT INTO download_run
                (year_label, source_url, status, started_at, finished_at, row_count)
            VALUES ('2024', 'http://example.test', 'failure',
                    '2026-01-01T00:00:00+00:00', '2026-01-01T02:00:00+00:00', NULL)
            """
        )
        db.commit()
        from tkdn_finder.db import _apply_migrations

        db.execute("DELETE FROM schema_version WHERE version = 13")
        _apply_migrations(db)

        rows = db.execute("SELECT * FROM year_count_snapshot").fetchall()
        assert rows == []
