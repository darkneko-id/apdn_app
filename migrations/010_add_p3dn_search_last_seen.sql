-- Migration 010: Track when a record was last seen on P3DN search results.
--
-- Rows imported directly from P3DN search.php (not from bulk export) have
-- masa_berlaku_akhir = NULL. p3dn_search_last_seen records the date the row
-- was last confirmed to appear in P3DN search results, enabling the UI to
-- distinguish "P3DN aktif today" from "not seen recently" vs "never scraped".

ALTER TABLE tkdn_certificate ADD COLUMN p3dn_search_last_seen DATE;

INSERT OR IGNORE INTO schema_version (version) VALUES (10);
