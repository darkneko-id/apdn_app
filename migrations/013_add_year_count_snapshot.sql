-- Migration 013: Daily snapshots of certificate count per year, for trend charts.
--
-- One row per (tahun_sumber, snapshot_date) — at most one snapshot per year per day.
-- Historical rows are backfilled from download_run.row_count (the source file's
-- row count for that run, not the deduped DB count) so the trend chart has data
-- before this feature existed. Go-forward snapshots taken by the app use the
-- actual deduped COUNT(*) from tkdn_certificate and will naturally diverge
-- from the backfilled approximation.

CREATE TABLE IF NOT EXISTS year_count_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date DATE NOT NULL,
    tahun_sumber INTEGER NOT NULL,
    cert_count INTEGER NOT NULL,
    UNIQUE(tahun_sumber, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_year_count_snapshot_tahun
    ON year_count_snapshot(tahun_sumber, snapshot_date);

INSERT OR IGNORE INTO year_count_snapshot (snapshot_date, tahun_sumber, cert_count)
SELECT
    date(dr.finished_at) AS snapshot_date,
    CAST(dr.year_label AS INTEGER) AS tahun_sumber,
    dr.row_count AS cert_count
FROM download_run dr
WHERE dr.status = 'success'
  AND dr.row_count IS NOT NULL
  AND dr.finished_at IS NOT NULL
  AND dr.year_label GLOB '[0-9][0-9][0-9][0-9]'
  AND dr.id = (
      SELECT MAX(dr2.id)
      FROM download_run dr2
      WHERE dr2.status = 'success'
        AND dr2.year_label = dr.year_label
        AND date(dr2.finished_at) = date(dr.finished_at)
  );

INSERT OR IGNORE INTO schema_version (version) VALUES (13);
