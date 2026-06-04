-- Migration 007: Add per-run inserted/updated/skipped counts to download_run.
--
-- row_count remains (total rows parsed from the source file).
-- inserted_count / updated_count / skipped_count track what actually changed in the DB.
-- NULL on old runs where these were not recorded.

ALTER TABLE download_run ADD COLUMN inserted_count INTEGER;
ALTER TABLE download_run ADD COLUMN updated_count  INTEGER;
ALTER TABLE download_run ADD COLUMN skipped_count  INTEGER;

INSERT OR IGNORE INTO schema_version (version) VALUES (7);
