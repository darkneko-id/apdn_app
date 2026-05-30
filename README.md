# TKDN Finder

Alat pencarian sertifikat **Tingkat Komponen Dalam Negeri (TKDN)** dari Kemenperin P3DN — dirancang untuk kegiatan pra-kualifikasi dan penyusunan BAHP di lingkungan KKKS (PTK-007 / Pedoman A7-001).

Data diunduh otomatis dari [p3dn.kemenperin.go.id](https://p3dn.kemenperin.go.id/rekap.php) dan diindeks untuk pencarian cepat dengan toleransi typo dan sinonim bilingual (Indonesia–Inggris).

---

## Fitur

- Pencarian cepat dengan toleransi typo dan sinonim (pompa ↔ pump, katup ↔ valve, dll.)
- Filter TKDN minimum, status validitas, KBLI, dan tahun
- Urutkan hasil berdasarkan perusahaan, nilai TKDN, atau masa berlaku
- Unduh hasil pencarian sebagai Excel (.xlsx)
- Detail sertifikat lengkap (Kode HS, KBLI, alamat, Tipe, Merk)
- Update Tipe produk dari portal tkdn.kemenperin.go.id
- Dark mode
- Download data otomatis saat pertama dijalankan
- Admin panel untuk refresh data dan manajemen sinonim

---

## Cara Setup (Pertama Kali)

### Opsi A — Python (Mac / Linux / Windows)

**Prasyarat:** Python 3.11+ dan [uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
# 1. Clone repo
git clone https://github.com/darkneko-id/apdn_app.git
cd apdn_app

# 2. Install dependencies
uv sync

# 3. (Opsional) Salin dan sesuaikan konfigurasi
cp config.example.yaml config.yaml

# 4. Jalankan
# Mac/Linux:
./run.sh
# Windows:
run.bat
```

Buka browser di **http://localhost:8000**

Saat pertama dijalankan dengan database kosong, aplikasi akan **otomatis mengunduh data TKDN** dari P3DN (sekitar 2–5 menit tergantung koneksi). Progress dapat dipantau di halaman Admin.

---

## Konfigurasi

Salin `config.example.yaml` ke `config.yaml` dan sesuaikan bila perlu:

```yaml
data_dir: data              # direktori penyimpanan database
log_level: INFO

p3dn:
  homepage_url: https://p3dn.kemenperin.go.id/rekap.php
  verify_ssl: true          # set false jika ada masalah SSL di jaringan korporat

schedule:
  enabled: false            # set true untuk refresh data otomatis harian
  cron: "0 2 * * *"        # jam 02:00 setiap hari
```

Atau via environment variable (prefix `TKDN_`):

```bash
TKDN_P3DN__VERIFY_SSL=false
TKDN_SCHEDULE__ENABLED=true
```

---

## Cara Pakai

### Pencarian

1. Ketik nama produk, perusahaan, spesifikasi, atau kode KBLI di kolom pencarian
2. Hasil muncul otomatis saat mengetik
3. Pencarian mendukung **typo** dan **sinonim** — "pompa" → "pump", "valve" → "katup"

### Filter

| Filter | Fungsi |
|--------|--------|
| TKDN Min (%) | Tampilkan hanya sertifikat dengan TKDN ≥ nilai ini |
| Hanya berlaku | Sembunyikan sertifikat kadaluarsa |
| KBLI | Filter berdasarkan klasifikasi industri (5 digit) |
| Tahun | Filter berdasarkan tahun penerbitan sertifikat |

### Status Sertifikat

| Status | Arti |
|--------|------|
| **Berlaku** | Aktif, masa berlaku > 60 hari |
| **Segera Berakhir** | Aktif, masa berlaku ≤ 60 hari — perlu konfirmasi ke vendor |
| **Kadaluarsa** | Sudah tidak berlaku |

### Update Tipe

Kolom Tipe tidak tersedia di ekspor bulk P3DN. Klik **Update Tipe** di hasil pencarian untuk mengisi data Tipe dari portal tkdn.kemenperin.go.id.

### Unduh Excel

Klik **Unduh Excel** untuk mengunduh hasil pencarian (maks. 500 baris) dalam format .xlsx.

### Admin

Buka `/admin` untuk refresh data, lihat riwayat download, dan kelola sinonim pencarian.

---

## Update Data

Data TKDN diunduh dari P3DN saat:
1. **Pertama kali dijalankan** (database kosong) — otomatis
2. **Klik "Refresh / Download Data"** di halaman Admin — manual
3. **Jadwal otomatis** — jika `schedule.enabled: true` di konfigurasi (default: jam 02:00)

---

## Stack Teknologi

| Layer | Teknologi |
|-------|-----------|
| Backend | FastAPI + Uvicorn |
| Database | SQLite + FTS5 |
| Frontend | HTMX + Tailwind CSS + Alpine.js |
| Scheduler | APScheduler |
| HTML Parsing | BeautifulSoup4 |
| Fuzzy Search | rapidfuzz |
| Config | pydantic-settings |

---

## Atribusi

- Data sumber: [Kemenperin P3DN](https://p3dn.kemenperin.go.id) (publik)
- Dikembangkan oleh Irsan H. Fadjri
