-- Add tipe column to FTS5 index so search box covers product type/variant keywords.
-- Must drop and recreate the virtual table because FTS5 does not support ALTER TABLE.

DROP TRIGGER IF EXISTS tkdn_ai;
DROP TRIGGER IF EXISTS tkdn_au;
DROP TRIGGER IF EXISTS tkdn_ad;
DROP TABLE IF EXISTS tkdn_search;

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

-- Repopulate from existing data
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
