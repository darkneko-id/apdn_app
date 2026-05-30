-- Migration 002: Add tipe to unique constraint so multiple tipe variants
-- of the same (company, product, spesifikasi) can be stored as distinct rows.
--
-- SQLite cannot ALTER a UNIQUE constraint, so we recreate the table.

PRAGMA foreign_keys=OFF;
BEGIN;

-- 1. New table with updated constraint and tipe NOT NULL DEFAULT ''
CREATE TABLE tkdn_certificate_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_perusahaan TEXT NOT NULL,
    nama_produk     TEXT NOT NULL,
    spesifikasi     TEXT NOT NULL DEFAULT '',
    merek           TEXT,
    tipe            TEXT NOT NULL DEFAULT '',
    nilai_tkdn      REAL,
    kode_hs         TEXT,
    kbli            TEXT,
    kelompok_barang TEXT,
    alamat          TEXT,
    provinsi        TEXT,
    masa_berlaku_akhir DATE,
    tahun_sumber    INTEGER,
    ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(nama_perusahaan, nama_produk, spesifikasi, tipe)
);

-- 2. Copy existing data (coerce NULL tipe → '')
INSERT INTO tkdn_certificate_new
    SELECT id, nama_perusahaan, nama_produk,
           COALESCE(spesifikasi, ''),
           merek,
           COALESCE(tipe, ''),
           nilai_tkdn, kode_hs, kbli, kelompok_barang,
           alamat, provinsi, masa_berlaku_akhir,
           tahun_sumber, ingested_at
    FROM tkdn_certificate;

-- 3. Drop old triggers (reference old table)
DROP TRIGGER IF EXISTS tkdn_ai;
DROP TRIGGER IF EXISTS tkdn_ad;
DROP TRIGGER IF EXISTS tkdn_au;

-- 4. Drop FTS index (content table is about to be replaced)
DROP TABLE IF EXISTS tkdn_search;

-- 5. Swap tables
DROP TABLE tkdn_certificate;
ALTER TABLE tkdn_certificate_new RENAME TO tkdn_certificate;

-- 6. Recreate FTS5
CREATE VIRTUAL TABLE tkdn_search USING fts5(
    nama_perusahaan,
    nama_produk,
    merek,
    spesifikasi,
    kbli,
    kelompok_barang,
    content='tkdn_certificate',
    content_rowid='id',
    tokenize='porter unicode61 remove_diacritics 2'
);

-- 7. Populate FTS from current data
INSERT INTO tkdn_search(rowid, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang)
    SELECT id, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang
    FROM tkdn_certificate;

-- 8. Recreate triggers
CREATE TRIGGER tkdn_ai AFTER INSERT ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(rowid, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang)
    VALUES (new.id, new.nama_perusahaan, new.nama_produk, new.merek, new.spesifikasi, new.kbli, new.kelompok_barang);
END;

CREATE TRIGGER tkdn_ad AFTER DELETE ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(tkdn_search, rowid, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang)
    VALUES ('delete', old.id, old.nama_perusahaan, old.nama_produk, old.merek, old.spesifikasi, old.kbli, old.kelompok_barang);
END;

CREATE TRIGGER tkdn_au AFTER UPDATE ON tkdn_certificate BEGIN
    INSERT INTO tkdn_search(tkdn_search, rowid, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang)
    VALUES ('delete', old.id, old.nama_perusahaan, old.nama_produk, old.merek, old.spesifikasi, old.kbli, old.kelompok_barang);
    INSERT INTO tkdn_search(rowid, nama_perusahaan, nama_produk, merek, spesifikasi, kbli, kelompok_barang)
    VALUES (new.id, new.nama_perusahaan, new.nama_produk, new.merek, new.spesifikasi, new.kbli, new.kelompok_barang);
END;

INSERT OR IGNORE INTO schema_version (version) VALUES (2);

COMMIT;
PRAGMA foreign_keys=ON;
