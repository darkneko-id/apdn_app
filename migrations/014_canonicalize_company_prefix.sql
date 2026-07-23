-- Migration 014: Canonicalise legal-entity prefixes in nama_perusahaan.
--
-- Problem: the (nama_perusahaan, nama_produk, spesifikasi, merek, nilai_tkdn,
-- tipe) UNIQUE dedup key compares nama_perusahaan as a raw string, so P3DN's
-- inconsistent prefix spellings ("PT. Bumi Kaya Steel" vs "PT Bumi Kaya Steel"
-- vs "pt.bumi kaya steel") were stored as separate companies.
--
-- Fix: rewrite the leading legal-entity prefix (PT/CV/UD/PD/Fa/NV) to one
-- canonical form — uppercase, no dot, single trailing space — so every
-- spelling collapses to the same string. Rows that become identical under the
-- UNIQUE key are merged (INSERT OR IGNORE keeps the lowest id). Go-forward
-- ingests apply the same rule in merger.py via textnorm.normalize_company_name;
-- the SQL below MUST stay in lockstep with that Python function.
--
-- This rebuilds tkdn_certificate (like migration 009), so it also re-creates
-- the FTS table, its sync triggers, and the B-tree indexes (migration 012).

PRAGMA foreign_keys=OFF;
BEGIN;

CREATE TABLE tkdn_certificate_new (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_perusahaan        TEXT NOT NULL,
    nama_produk            TEXT NOT NULL,
    spesifikasi            TEXT NOT NULL DEFAULT '',
    merek                  TEXT NOT NULL DEFAULT '',
    tipe                   TEXT NOT NULL DEFAULT '',
    nilai_tkdn             REAL,
    kode_hs                TEXT,
    kbli                   TEXT,
    kelompok_barang        TEXT,
    alamat                 TEXT,
    provinsi               TEXT,
    masa_berlaku_akhir     DATE,
    tahun_sumber           INTEGER,
    ingested_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    p3dn_search_last_seen  DATE,
    p3dn_not_found_since   DATE,
    UNIQUE(nama_perusahaan, nama_produk, spesifikasi, merek, nilai_tkdn, tipe)
);

-- Canonicalise the leading two-character prefix: when the first two characters
-- are a known legal-entity abbreviation and the third character is a dot or a
-- space, rewrite to UPPER(prefix) + ' ' + the remainder with leading dots and
-- spaces stripped. RTRIM guards the pathological "PT."-only name from gaining
-- a trailing space. Everything else is copied unchanged.
INSERT OR IGNORE INTO tkdn_certificate_new
    SELECT id,
           CASE
               WHEN UPPER(SUBSTR(nama_perusahaan, 1, 2)) IN ('PT','CV','UD','PD','FA','NV')
                    AND SUBSTR(nama_perusahaan, 3, 1) IN ('.', ' ')
               THEN RTRIM(
                        UPPER(SUBSTR(nama_perusahaan, 1, 2)) || ' ' ||
                        LTRIM(SUBSTR(nama_perusahaan, 3), '. ')
                    )
               ELSE nama_perusahaan
           END,
           nama_produk,
           COALESCE(spesifikasi, ''),
           COALESCE(merek, ''),
           COALESCE(tipe, ''),
           nilai_tkdn, kode_hs, kbli, kelompok_barang,
           alamat, provinsi, masa_berlaku_akhir,
           tahun_sumber, ingested_at,
           p3dn_search_last_seen, p3dn_not_found_since
    FROM tkdn_certificate
    ORDER BY id;

DROP TRIGGER IF EXISTS tkdn_ai;
DROP TRIGGER IF EXISTS tkdn_ad;
DROP TRIGGER IF EXISTS tkdn_au;
DROP TABLE IF EXISTS tkdn_search;
DROP TABLE tkdn_certificate;
ALTER TABLE tkdn_certificate_new RENAME TO tkdn_certificate;

CREATE VIRTUAL TABLE tkdn_search USING fts5(
    nama_perusahaan,
    nama_produk,
    merek,
    tipe,
    spesifikasi,
    kbli,
    kelompok_barang,
    content='tkdn_certificate',
    content_rowid='id',
    tokenize='porter unicode61 remove_diacritics 2'
);

INSERT INTO tkdn_search(rowid, nama_perusahaan, nama_produk, merek, tipe, spesifikasi, kbli, kelompok_barang)
    SELECT id, nama_perusahaan, nama_produk, merek, tipe, spesifikasi, kbli, kelompok_barang
    FROM tkdn_certificate;

CREATE TRIGGER tkdn_ai AFTER INSERT ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(rowid, nama_perusahaan, nama_produk, merek, tipe, spesifikasi, kbli, kelompok_barang)
    VALUES (new.id, new.nama_perusahaan, new.nama_produk, new.merek, new.tipe, new.spesifikasi, new.kbli, new.kelompok_barang);
END;

CREATE TRIGGER tkdn_ad AFTER DELETE ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(tkdn_search, rowid, nama_perusahaan, nama_produk, merek, tipe, spesifikasi, kbli, kelompok_barang)
    VALUES ('delete', old.id, old.nama_perusahaan, old.nama_produk, old.merek, old.tipe, old.spesifikasi, old.kbli, old.kelompok_barang);
END;

CREATE TRIGGER tkdn_au AFTER UPDATE ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(tkdn_search, rowid, nama_perusahaan, nama_produk, merek, tipe, spesifikasi, kbli, kelompok_barang)
    VALUES ('delete', old.id, old.nama_perusahaan, old.nama_produk, old.merek, old.tipe, old.spesifikasi, old.kbli, old.kelompok_barang);
    INSERT INTO tkdn_search(rowid, nama_perusahaan, nama_produk, merek, tipe, spesifikasi, kbli, kelompok_barang)
    VALUES (new.id, new.nama_perusahaan, new.nama_produk, new.merek, new.tipe, new.spesifikasi, new.kbli, new.kelompok_barang);
END;

CREATE INDEX IF NOT EXISTS idx_cert_kbli
    ON tkdn_certificate(kbli);
CREATE INDEX IF NOT EXISTS idx_cert_tahun_sumber
    ON tkdn_certificate(tahun_sumber);
CREATE INDEX IF NOT EXISTS idx_cert_validity_tkdn
    ON tkdn_certificate(masa_berlaku_akhir, nilai_tkdn);

INSERT OR IGNORE INTO schema_version (version) VALUES (14);

COMMIT;
PRAGMA foreign_keys=ON;
