# Panduan Instalasi & Penggunaan — TKDN Finder Portable

> Panduan ini untuk pengguna yang menerima file **`tkdn-finder-portable.zip`** dan ingin menjalankan TKDN Finder tanpa perlu menginstal Python.

---

## Isi Paket

Setelah ZIP diekstrak, folder berisi:

```
tkdn-finder-portable/
├── tkdn-finder.exe        ← aplikasi utama (Windows)
├── run.bat                ← launcher Windows (klik dua kali di sini)
├── config.example.yaml   ← contoh konfigurasi (opsional)
└── HOWTO_PORTABLE.md     ← panduan ini
```

> **Data dan database** disimpan secara otomatis di `%APPDATA%\TKDN-Finder\` (biasanya `C:\Users\<nama-user>\AppData\Roaming\TKDN-Finder\`). Folder ini dibuat otomatis saat pertama kali dijalankan.

---

## Langkah 1 — Ekstrak ZIP

Klik kanan file `tkdn-finder-portable.zip` → **Extract All…** → pilih folder tujuan, misalnya:

```
C:\Tools\TKDN-Finder\
```

Jangan jalankan `.exe` langsung dari dalam ZIP — ekstrak dulu.

---

## Langkah 2 — Jalankan Aplikasi

Klik dua kali **`run.bat`** (atau `tkdn-finder.exe` jika ingin langsung).

Jendela command prompt akan muncul dengan pesan:

```
Starting TKDN Finder...
Buka browser di http://localhost:8000
Tekan Ctrl+C untuk berhenti.
```

**Biarkan jendela ini tetap terbuka** selama menggunakan aplikasi. Menutup jendela ini akan menghentikan server.

### Peringatan Windows SmartScreen / Antivirus

Karena file `.exe` tidak ditandatangani secara digital, Windows mungkin menampilkan peringatan:

> *"Windows protected your PC"*

Klik **"More info"** → **"Run anyway"** untuk melanjutkan. Ini normal untuk aplikasi portable yang tidak dikomersilkan.

Jika antivirus memblokir, tambahkan folder instalasi ke daftar pengecualian (exclusion list) antivirus Anda.

---

## Langkah 3 — Buka di Browser

Buka browser (Chrome, Edge, Firefox) dan masuk ke:

```
http://localhost:8000
```

---

## Langkah 4 — Download Data (Pertama Kali)

Saat pertama kali dijalankan dengan database kosong, aplikasi akan **otomatis mengunduh data TKDN** dari portal P3DN Kemenperin.

- Proses berlangsung sekitar **2–10 menit** tergantung koneksi internet
- Progress dapat dipantau di halaman **Admin** (`http://localhost:8000/admin`)
- Selama proses berlangsung, halaman pencarian menampilkan pesan "Sedang mengunduh data..."
- Setelah selesai, data langsung dapat dicari tanpa restart

Untuk update data di kemudian hari: buka `/admin` → klik **"Refresh / Download Data"**.

---

## Konfigurasi (Opsional)

Jika tidak ada file konfigurasi, aplikasi berjalan dengan pengaturan default. Untuk menyesuaikan:

1. Salin `config.example.yaml` → `config.yaml` (di folder yang sama dengan `tkdn-finder.exe`)
2. Edit sesuai kebutuhan:

```yaml
data_dir: "data"       # diabaikan di Windows; data selalu ke %APPDATA%\TKDN-Finder\
log_level: "INFO"

p3dn:
  verify_ssl: false    # set false jika ada masalah SSL di jaringan korporat/proxy
  download_timeout_seconds: 120

schedule:
  enabled: true        # set true untuk refresh data otomatis setiap hari jam 02:00
  cron: "0 2 * * *"
```

Konfigurasi juga bisa diset via **environment variable** tanpa file YAML:

| Variabel | Contoh | Keterangan |
|----------|--------|------------|
| `TKDN_P3DN__VERIFY_SSL` | `false` | Matikan verifikasi SSL |
| `TKDN_SCHEDULE__ENABLED` | `true` | Aktifkan refresh otomatis |
| `TKDN_LOG_LEVEL` | `DEBUG` | Level log |

---

## Masalah Umum

### Halaman tidak bisa dibuka di browser

Pastikan jendela command prompt masih terbuka dan menampilkan pesan server aktif. Coba akses `http://127.0.0.1:8000` (bukan `localhost`) jika browser menolak.

### Error saat download data: SSL / certificate error

Jaringan korporat sering menggunakan proxy yang mengintervensi koneksi HTTPS. Tambahkan ke `config.yaml`:

```yaml
p3dn:
  verify_ssl: false
```

> Catatan: `verify_ssl: false` menonaktifkan verifikasi sertifikat SSL. Gunakan hanya di jaringan internal yang terpercaya.

### Port 8000 sudah dipakai aplikasi lain

Jalankan dari command prompt dengan port berbeda:

```cmd
tkdn-finder.exe --port 8080
```

Lalu buka `http://localhost:8080`.

### Antivirus menghapus `tkdn-finder.exe`

Tambahkan folder instalasi ke exclusion list antivirus. File `.exe` dihasilkan dari kode sumber Python menggunakan PyInstaller — tidak mengandung malware.

### Bagaimana melihat log error?

Jalankan dari command prompt (`cmd`) secara manual untuk melihat output lengkap:

```cmd
cd C:\Tools\TKDN-Finder
tkdn-finder.exe
```

---

## Cara Menghentikan Aplikasi

Tekan **Ctrl+C** di jendela command prompt, atau tutup jendela tersebut.

---

## Lokasi Data

| Item | Lokasi (Windows) |
|------|-----------------|
| Database SQLite | `%APPDATA%\TKDN-Finder\tkdn.db` |
| File raw download | `%APPDATA%\TKDN-Finder\raw\` |
| Konfigurasi | `config.yaml` (di folder yang sama dengan .exe) |

Untuk backup atau pindah komputer: salin folder `%APPDATA%\TKDN-Finder\` ke komputer baru, lalu jalankan `run.bat`. Data tidak perlu diunduh ulang.

---

## Cara Update ke Versi Baru

1. Unduh `tkdn-finder-portable.zip` versi terbaru
2. Ekstrak ke folder yang sama (timpa file lama)
3. Jalankan `run.bat` seperti biasa

Database di `%APPDATA%\TKDN-Finder\` tidak akan terhapus — data tetap tersimpan dan migrasi schema dijalankan otomatis.

---

*Data sumber: [Kemenperin P3DN](https://p3dn.kemenperin.go.id) (publik) — dikembangkan oleh Irsan H. Fadjri*
