#!/usr/bin/env bash
# Bedah runner ab95 tanpa menarik seluruh 744 baris ke dalam konteks.
# Tujuan: menemukan MENGAPA 'kandidat_per_strategi' kosong pada hasil backtest,
# dan mendapatkan tanda tangan fungsi pembantu yang bisa dipakai ulang.
set -uo pipefail
AB="${AB95_PATH:-klon_modul/scripts/ab95.py}"
mkdir -p hasil/bt95
OUT=hasil/bt95/bedah_runner.txt

{
  echo "berkas=$AB"
  if [ ! -f "$AB" ]; then
    echo "BERKAS TIDAK ADA"
    exit 0
  fi
  echo "baris_total=$(wc -l < "$AB")"
  echo "md5=$(md5sum "$AB" | cut -d' ' -f1)"

  echo
  echo "=== 1) definisi tingkat atas (tanda tangan) ==="
  grep -n '^def \|^class \|^KONFIG\|^MODAL_AWAL\|^HORIZON\|^BENDERA' "$AB"

  echo
  echo "=== 2) semua kemunculan kandidat/menang per strategi ==="
  grep -n 'kandidat_per_strategi\|menang_per_strategi' "$AB"

  echo
  echo "=== 3) blok +-8 baris di sekitar kandidat_per_strategi ==="
  grep -n -B8 -A8 'kandidat_per_strategi' "$AB"

  A=$(grep -n '^def cmd_backtest' "$AB" | head -1 | cut -d: -f1)
  if [ -n "$A" ]; then
    B=$(awk -v a="$A" 'NR>a && /^def /{print NR; exit}' "$AB")
    [ -n "$B" ] || B=$(wc -l < "$AB")
    echo
    echo "=== 4) cmd_backtest baris $A..$B (baris relevan saja) ==="
    sed -n "${A},${B}p" "$AB" | grep -n 'kandidat\|menang\|ringkas\|per_kelompok\|per_arah\|Counter\|for \|append\|update\|setdefault\|total\[' 
  fi

  echo
  echo "=== 5) tanda tangan pembantu yang akan dipakai ulang ==="
  grep -n -A3 '^def daftar_simbol\|^def muat_plane\|^def buat_backtester\|^def buat_pipeline\|^def metrik\|^def potong_plane\|^def tulis' "$AB"
} > "$OUT" 2>&1

echo "bedah selesai -> $OUT"
wc -l < "$OUT"
