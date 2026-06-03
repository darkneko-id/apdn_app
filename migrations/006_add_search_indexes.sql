-- Migration 006: Add B-tree indexes for filtered search queries.
--
-- Covers columns used as WHERE predicates in search.py:
--   kbli         = ?          (equality)
--   tahun_sumber = ?          (equality)
--   masa_berlaku_akhir >= ?   (range — leading column of compound index)
--   nilai_tkdn   >= ?         (range — trailing column of compound index)
--
-- The compound index (masa_berlaku_akhir, nilai_tkdn) covers both
-- validity-only queries (leading column) and combined validity+tkdn_min
-- queries (both columns). No separate single-column index on nilai_tkdn
-- is needed because tkdn_min defaults to 0.0 and is rarely the sole filter.

CREATE INDEX IF NOT EXISTS idx_cert_kbli
    ON tkdn_certificate(kbli);

CREATE INDEX IF NOT EXISTS idx_cert_tahun_sumber
    ON tkdn_certificate(tahun_sumber);

CREATE INDEX IF NOT EXISTS idx_cert_validity_tkdn
    ON tkdn_certificate(masa_berlaku_akhir, nilai_tkdn);

INSERT OR IGNORE INTO schema_version (version) VALUES (6);
