# uji-trading — rumah tunggal pengujian & pencatatan

Repo ini adalah **satu-satunya tempat** hasil pengujian modul trading LUX dicatat.
Setiap kesimpulan harus bisa ditelusuri ke berkas bukti di `hasil/`.

## Mengapa pengujian pindah ke akun ini

Bukti, bukan asumsi:

- Di akun `EnVyxS`, GitHub Actions **berhenti dijalankan**. Pesan tab Actions:
  *"The job was not started because recent account payments have failed or your
  spending limit needs to be increased."*
- Kanari (workflow paling minimal: checkout → tulis 1 berkas → commit balik)
  di-push ke `EnVyxS/uji-trading` pada `2026-08-05T07:15:07Z` dan **tidak pernah
  menghasilkan commit**. Empat push sebelumnya juga senyap.
- Kanari yang **sama persis** di `ReNvYxs/uji-kanari` selesai dan commit balik
  pada `2026-08-05T07:39:51Z`.

Karena workflow-nya identik, penyebabnya bukan kode workflow melainkan
kuota/billing di level akun.

## Kapabilitas runner yang sudah dibuktikan

Sumber: `ReNvYxs/uji-kanari` → `hasil/kanari.txt`.

| Uji | Hasil |
|---|---|
| Klon `EnVyxS/lux-modul-trading` tanpa auth | rc=0 — bisa |
| Klon `EnVyxS/uji-trading` tanpa auth | rc=0 — bisa |
| Klon `EnVyxS/lux-ai-research` tanpa auth | rc=0 — bisa |
| Klon `EnVyxS/lux-trading-strategy` tanpa auth | rc=128 — masih privat |
| Unduh aset dataset 95 pair tanpa auth | HTTP 206 — bisa |
| Metadata release tanpa auth | HTTP 200 — bisa |
| `secrets.LUX_PAT` tersedia? | tidak — dan **tidak lagi dibutuhkan** |

Runner: Ubuntu, 4 vCPU, ~16 GB RAM, ~88 GB disk.

## Arsitektur

1. Modul yang diuji **tidak disalin** ke repo ini. Ia diklon pada SHA yang dipin
   (`MODUL_REF` di `.github/workflows/bt95.yml`) agar tidak ada versi bayangan
   dan agar setiap hasil terikat ke satu revisi yang bisa diverifikasi.
2. Dataset 95 pair diunduh dari release `EnVyxS/uji-trading`; **sha256 wajib
   cocok** dengan nilai yang dipin, kalau tidak job gagal keras.
3. Setiap tahap menulis bukti ke `hasil/bt95/` lalu **commit balik**, sehingga
   kegagalan di tengah tetap meninggalkan jejak yang bisa dibaca.
4. Repo ini publik dan **tidak boleh** memuat kredensial apa pun.

## Struktur

- `.github/workflows/bt95.yml` — pipeline backtest 95 pair
- `alat/siapkan.sh` — klon modul (SHA dipin) + unduh & verifikasi dataset
- `alat/rekam.sh` — commit balik bukti
- `hasil/bt95/` — bukti aktual dari runner
