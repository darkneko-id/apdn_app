-- Track when a P3DN search run confirmed a record is absent from P3DN search results.
-- Set to today after a successful company scrape that did NOT include this record.
-- Cleared when the record IS found in a subsequent scrape.
ALTER TABLE tkdn_certificate ADD COLUMN p3dn_not_found_since DATE;
INSERT OR IGNORE INTO schema_version (version) VALUES (11);
