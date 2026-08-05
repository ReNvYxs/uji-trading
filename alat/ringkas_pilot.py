#!/usr/bin/env python3
"""Indeks seluruh artefak JSON di hasil/bt95 supaya mudah diaudit."""
import glob
import json
import os

WAJIB = (
    "inventaris_dataset.json",
    "RINGKAS_INVENTARIS.json",
    "probe_kandidat.json",
    "pilot_integritas_single_15m.json",
    "pilot_integritas_single_4h.json",
    "analisa_single_15m_asli.json",
    "analisa_single_4h_asli.json",
    "analisa_single_4h_final_bar_per_hari.json",
)

KUNCI_TOTAL = (
    "trade",
    "menang",
    "win_rate",
    "pnl_bersih",
    "pnl_kotor",
    "biaya",
    "pf_bersih",
    "pf_kotor",
    "expectancy_r",
)

ring = {"berkas": {}}
for p in sorted(glob.glob("hasil/bt95/*.json")):
    nama = os.path.basename(p)
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        info = {"ok": True, "byte": os.path.getsize(p)}
        if isinstance(d, dict):
            info["kunci"] = sorted(d)[:40]
            for k in ("lulus", "terpotong_batas_waktu", "simbol_diproses", "detik"):
                if k in d:
                    info[k] = d[k]
            if isinstance(d.get("total"), dict):
                t = d["total"]
                info["total"] = {k: t.get(k) for k in KUNCI_TOTAL}
            if isinstance(d.get("varian"), dict):
                info["varian"] = d["varian"]
        ring["berkas"][nama] = info
    except Exception as e:
        ring["berkas"][nama] = {"ok": False, "galat": str(e)[:200]}

ring["hilang"] = [n for n in WAJIB if not os.path.exists("hasil/bt95/" + n)]
ring["lengkap"] = not ring["hilang"]

with open("hasil/bt95/RINGKASAN.json", "w", encoding="utf-8") as fh:
    json.dump(ring, fh, indent=1, sort_keys=True, ensure_ascii=False)
print(json.dumps(ring, indent=1, ensure_ascii=False)[:4000])
