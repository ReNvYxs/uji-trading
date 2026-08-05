#!/usr/bin/env python3
"""Reduksi inventaris dataset menjadi ringkasan yang bisa dibaca.

Inventaris mentah memuat satu entri per berkas (476 berkas, ~125 KB), terlalu
besar untuk dibaca utuh. Skrip ini TIDAK membuang bukti - berkas mentah tetap
disimpan - ia hanya:
  1. meneruskan verdict tingkat atas milik modul itu sendiri,
  2. mengagregasi bendera masalah per berkas,
  3. menandai berkas/simbol yang secara struktural mencurigakan.
"""
import json
import os

MENTAH = "hasil/bt95/inventaris_dataset.json"
KELUARAN = "hasil/bt95/RINGKAS_INVENTARIS.json"

BENDERA = (
    "duplikat_ts",
    "ts_menurun",
    "celah",
    "bar_hilang",
    "nilai_tidak_hingga",
    "ohlc_rusak",
    "volume_nol",
)

ATAS = (
    "perintah",
    "data_dir",
    "lulus",
    "detik",
    "jumlah_simbol",
    "jumlah_berkas_csv",
    "berkas_diperiksa",
    "jumlah_berkas_bermasalah",
    "terpotong_batas_waktu",
    "tf_tersedia",
)

if not os.path.exists(MENTAH):
    print("inventaris mentah belum ada, dilewati")
    raise SystemExit(0)

with open(MENTAH, encoding="utf-8") as fh:
    data = json.load(fh)

entri = []


def jelajah(o, jalur=""):
    if isinstance(o, dict):
        if any(k in o for k in BENDERA):
            entri.append((jalur, o))
            return
        for k, v in o.items():
            jelajah(v, (jalur + "/" + str(k)) if jalur else str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            jelajah(v, jalur + "[" + str(i) + "]")


jelajah(data)

# Hanya entri di bawah 'rinci/' adalah per-berkas; sisanya agregat, jangan dicampur.
berkas = [(j, e) for j, e in entri if j.startswith("rinci/")]
agregat = [j for j, _ in entri if not j.startswith("rinci/")]


def besaran(v):
    if v is True:
        return 1
    if isinstance(v, bool):
        return 0
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, (list, tuple, dict, str)):
        return len(v)
    return 0


def nama(jalur):
    return jalur.split("/")[-1]


def simbol(jalur):
    return nama(jalur).rsplit("_", 1)[0]


agg = {
    "berkas_mentah": MENTAH,
    "byte_mentah": os.path.getsize(MENTAH),
    "verdict_modul": {k: data.get(k) for k in ATAS if k in data},
    "per_tf": data.get("per_tf"),
    "jumlah_entri_per_berkas": len(berkas),
    "jalur_agregat_diabaikan": agregat[:10],
    "bendera": {},
}

bm = data.get("berkas_bermasalah")
if bm is not None:
    try:
        n = len(bm)
    except TypeError:
        n = None
    agg["berkas_bermasalah"] = {
        "jumlah": n,
        "contoh": (list(bm)[:40] if n else bm),
    }

for b in BENDERA:
    kena = []
    for jalur, e in berkas:
        n = besaran(e.get(b))
        if n:
            kena.append([nama(jalur), n])
    kena.sort(key=lambda t: -t[1])
    agg["bendera"][b] = {
        "jumlah_berkas_kena": len(kena),
        "total": sum(t[1] for t in kena),
        "terburuk": kena[:12],
    }


def sebaran(kunci_kandidat):
    nilai = []
    for _, e in berkas:
        for k in kunci_kandidat:
            v = e.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                nilai.append(v)
                break
    if not nilai:
        return None
    nilai.sort()
    return {
        "min": nilai[0],
        "p10": nilai[max(0, len(nilai) // 10)],
        "median": nilai[len(nilai) // 2],
        "maks": nilai[-1],
        "n": len(nilai),
    }


agg["sebaran_bar"] = sebaran(("bar", "bar_total", "jumlah_bar", "n_bar"))
agg["sebaran_hari"] = sebaran(("hari",))

# --- higiene: riwayat pendek ---
pendek = []
for jalur, e in berkas:
    h = e.get("hari")
    if isinstance(h, (int, float)) and not isinstance(h, bool) and h < 150:
        pendek.append([nama(jalur), h, e.get("bar")])
pendek.sort(key=lambda t: t[1])
agg["riwayat_pendek"] = {
    "kriteria": "hari < 150",
    "jumlah_berkas": len(pendek),
    "simbol": sorted({p[0].rsplit("_", 1)[0] for p in pendek}),
    "terpendek": pendek[:25],
}

# --- higiene: instrumen yang tampaknya bukan pasar 24/7 ---
# volume nol pada bar 5m adalah tanda khas instrumen dengan jam perdagangan
# terbatas (saham/ETF), bukan perpetual kripto yang berdagang terus-menerus.
vol0 = {}
for jalur, e in berkas:
    n = besaran(e.get("volume_nol"))
    if n:
        vol0.setdefault(simbol(jalur), 0)
        vol0[simbol(jalur)] += n
agg["simbol_dengan_volume_nol"] = {
    "catatan": "kandidat instrumen non-24/7 (saham/ETF) di dalam dataset 'pair'",
    "jumlah_simbol": len(vol0),
    "rinci": dict(sorted(vol0.items(), key=lambda t: -t[1])),
}

agg["bersih_semua_bendera"] = all(
    v["jumlah_berkas_kena"] == 0 for v in agg["bendera"].values()
)

with open(KELUARAN, "w", encoding="utf-8") as fh:
    json.dump(agg, fh, indent=1, ensure_ascii=False, sort_keys=True)

print(json.dumps(agg, indent=1, ensure_ascii=False)[:6000])
