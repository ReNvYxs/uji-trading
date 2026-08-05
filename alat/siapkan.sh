#!/usr/bin/env bash
# Menyiapkan bahan uji TANPA PAT: kedua repo sumber sudah publik.
#  - Modul diklon pada SHA yang DIPIN (bukan 'main' yang bisa bergerak).
#  - Dataset 95 pair diunduh dari release, sha256 WAJIB cocok.
set -uo pipefail
export GIT_TERMINAL_PROMPT=0

: "${MODUL_REPO:?MODUL_REPO wajib}"
: "${MODUL_REF:?MODUL_REF wajib}"
: "${DATASET_REPO:?DATASET_REPO wajib}"
: "${ASET_ID:?ASET_ID wajib}"
: "${ASET_SHA256:?ASET_SHA256 wajib}"

mkdir -p hasil/bt95
LOG=hasil/bt95/log_siapkan.txt
: > "$LOG"
rm -f hasil/bt95/GAGAL_siapkan.txt

gagal() {
  printf 'GAGAL: %s\n' "$1" | tee -a "$LOG" > hasil/bt95/GAGAL_siapkan.txt
  exit "$2"
}

{
  echo "utc_mulai=$(date -u +%FT%TZ)"
  echo "modul_repo=$MODUL_REPO"
  echo "modul_ref=$MODUL_REF"
  echo "dataset_repo=$DATASET_REPO"
  echo "aset_id=$ASET_ID"
} >> "$LOG"

# --- 1) modul pada SHA yang dipin, anonim ---
rm -rf klon_modul
mkdir -p klon_modul
(
  cd klon_modul
  git init -q
  git remote add origin "https://github.com/$MODUL_REPO.git"
  git fetch -q --depth 1 origin "$MODUL_REF"
  git checkout -q FETCH_HEAD
) >> "$LOG" 2>&1

if [ ! -d klon_modul/lux_modul ]; then
  echo "fetch-by-sha gagal, fallback klon penuh" >> "$LOG"
  rm -rf klon_modul
  git clone -q "https://github.com/$MODUL_REPO.git" klon_modul >> "$LOG" 2>&1
  git -C klon_modul checkout -q "$MODUL_REF" >> "$LOG" 2>&1
fi
[ -d klon_modul/lux_modul ] || gagal "klon modul gagal atau lux_modul/ tidak ada" 3

echo "modul_head=$(git -C klon_modul rev-parse HEAD)" >> "$LOG"
find klon_modul/lux_modul -name '*.py' -print0 | sort -z | xargs -0 md5sum | sed 's#klon_modul/##' > hasil/bt95/manifest_modul.txt
echo "modul_jumlah_py=$(wc -l < hasil/bt95/manifest_modul.txt)" >> "$LOG"

[ -f klon_modul/scripts/ab95.py ] || gagal "scripts/ab95.py tidak ada di modul" 5
cp klon_modul/scripts/ab95.py hasil/bt95/runner_ab95.py
echo "md5_runner_ab95=$(md5sum klon_modul/scripts/ab95.py | cut -d' ' -f1)" >> "$LOG"
echo "requirements=$(tr '\n' ' ' < klon_modul/requirements.txt)" >> "$LOG"

# --- 2) dataset 95 pair, anonim, sha256 wajib cocok ---
curl -sSL --fail-with-body -H 'Accept: application/octet-stream' -o 95pair.zip \
  "https://api.github.com/repos/$DATASET_REPO/releases/assets/$ASET_ID" >> "$LOG" 2>&1 \
  || gagal "unduh aset dataset gagal" 6
BYTE=$(stat -c%s 95pair.zip)
SHA=$(sha256sum 95pair.zip | cut -d' ' -f1)
echo "dataset_byte=$BYTE" >> "$LOG"
echo "dataset_sha256=$SHA" >> "$LOG"
[ "$SHA" = "$ASET_SHA256" ] || gagal "sha256 dataset tidak cocok (dapat $SHA)" 7

rm -rf dataset
mkdir -p dataset/ekstrak
# unzip rc=1 berarti PERINGATAN (mis. nama berkas non-ASCII), bukan kegagalan.
# Gate sebenarnya adalah keberadaan CSV, bukan status keluar unzip.
unzip -q -o 95pair.zip -d dataset/ekstrak >> "$LOG" 2>&1
RC_UNZIP=$?
echo "unzip_rc=$RC_UNZIP" >> "$LOG"
[ "$RC_UNZIP" -le 1 ] || gagal "ekstrak zip gagal keras (rc=$RC_UNZIP)" 8

CONTOH=$(find dataset/ekstrak -name '*_4h.csv' -print -quit)
[ -n "$CONTOH" ] || gagal "tidak menemukan *_4h.csv setelah ekstrak" 9
DATA_DIR=$(dirname "$CONTOH")
echo "data_dir=$DATA_DIR" >> "$LOG"
echo "jumlah_csv_total=$(find "$DATA_DIR" -name '*.csv' | wc -l)" >> "$LOG"
for tf in 5m 15m 1h 4h 1d; do
  echo "jumlah_csv_$tf=$(find "$DATA_DIR" -name "*_$tf.csv" | wc -l)" >> "$LOG"
done
find "$DATA_DIR" -name '*_4h.csv' -printf '%f\n' | sort > hasil/bt95/daftar_simbol_4h.txt

# Higiene data: catat simbol dengan nama berkas non-ASCII (bukan simbol Binance wajar)
find "$DATA_DIR" -name '*.csv' -printf '%f\n' | LC_ALL=C grep '[^ -~]' | sort > hasil/bt95/berkas_nonascii.txt || true
echo "jumlah_berkas_nonascii=$(wc -l < hasil/bt95/berkas_nonascii.txt)" >> "$LOG"
echo "byte_dataset_terekstrak=$(du -sb "$DATA_DIR" | cut -f1)" >> "$LOG"

{
  echo "LUX_AKAR=klon_modul"
  echo "LUX_DATA_DIR=$DATA_DIR"
  echo "MODUL_SHA=$MODUL_REF"
} >> "${GITHUB_ENV:-/dev/null}"

echo "utc_selesai=$(date -u +%FT%TZ)" >> "$LOG"
echo "siapkan=OK" >> "$LOG"
