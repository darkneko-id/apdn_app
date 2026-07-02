-- Migration 012: Restore B-tree indexes dropped by migration 009's table recreation.
--
-- Migration 009 did DROP TABLE tkdn_certificate + CREATE TABLE to widen the
-- UNIQUE key, which silently dropped the indexes migration 006 created.
-- Re-create them here; no later migration should DROP TABLE tkdn_certificate
-- again without repeating this step.

CREATE INDEX IF NOT EXISTS idx_cert_kbli
    ON tkdn_certificate(kbli);

CREATE INDEX IF NOT EXISTS idx_cert_tahun_sumber
    ON tkdn_certificate(tahun_sumber);

CREATE INDEX IF NOT EXISTS idx_cert_validity_tkdn
    ON tkdn_certificate(masa_berlaku_akhir, nilai_tkdn);

INSERT OR IGNORE INTO schema_version (version) VALUES (12);
