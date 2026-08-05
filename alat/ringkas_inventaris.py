#!/usr/bin/env python3
"""Reduksi inventaris dataset menjadi ringkasan yang bisa dibaca.

Inventaris mentah memuat satu entri per berkas (476 berkas), terlalu besar untuk
dibaca utuh. Skrip ini TIDAK membuang bukti - berkas mentah tetap ada - ia hanya
menghitung agregat dan menonjolkan pelanggaran terburuk.
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


agg = {
    "berkas_mentah": MENTAH,
    "byte_mentah": os.path.getsize(MENTAH),
    "kunci_tingkat_atas": sorted(data) if isinstance(data, dict) else None,
    "jumlah_entri_berkas": len(entri),
    "bendera": {},
}

for b in BENDERA:
    kena = []
    for jalur, e in entri:
        n = besaran(e.get(b))
        if n:
            kena.append([jalur, n])
    kena.sort(key=lambda t: -t[1])
    agg["bendera"][b] = {
        "jumlah_berkas_kena": len(kena),
        "total": sum(t[1] for t in kena),
        "terburuk": kena[:10],
    }


def sebaran(nama, kunci_kandidat):
    nilai = []
    for _, e in entri:
        for k in kunci_kandidat:
            v = e.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                nilai.append(v)
                break
    if not nilai:
        return
    nilai.sort()
    agg[nama] = {
        "min": nilai[0],
        "median": nilai[len(nilai) // 2],
        "maks": nilai[-1],
        "total": sum(nilai),
        "n": len(nilai),
    }


sebaran("bar", ("bar", "bar_total", "jumlah_bar", "n_bar"))
sebaran("hari", ("hari",))

agg["bersih"] = all(v["jumlah_berkas_kena"] == 0 for v in agg["bendera"].values())

with open(KELUARAN, "w", encoding="utf-8") as fh:
    json.dump(agg, fh, indent=1, ensure_ascii=False, sort_keys=True)

print(json.dumps(agg, indent=1, ensure_ascii=False)[:5000])
