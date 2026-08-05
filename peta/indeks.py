#!/usr/bin/env python3
"""Indeks artefak peta TF: satu berkas untuk melihat semua konfig sekaligus."""
import json
import os

DIR = "hasil/peta"
KELUARAN = os.path.join(DIR, "INDEKS.json")
KUNCI = (
    "trade",
    "win_rate",
    "pnl_bersih",
    "pnl_kotor",
    "biaya",
    "pf_bersih",
    "pf_kotor",
    "biaya_per_trade",
    "edge_kotor_per_trade",
    "expectancy_r",
)

out = {"berkas": {}, "peta_tf": {}}
for nama in sorted(os.listdir(DIR)) if os.path.isdir(DIR) else []:
    if not nama.endswith(".json") or nama == "INDEKS.json":
        continue
    jalur = os.path.join(DIR, nama)
    rec = {"byte": os.path.getsize(jalur)}
    try:
        with open(jalur, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception as e:
        rec["ok"] = False
        rec["galat"] = str(e)[:200]
        out["berkas"][nama] = rec
        continue
    rec["ok"] = True
    for k in ("simbol_diproses", "terpotong_batas_waktu", "detik", "entry_tf"):
        if k in d:
            rec[k] = d[k]
    tot = d.get("total") or {}
    rec["total"] = {k: tot.get(k) for k in KUNCI if k in tot}
    rec["layak"] = d.get("daftar_strategi_layak")
    rec["rugi_dua_paruh"] = d.get("daftar_strategi_rugi_dua_paruh")
    rec["galat_isi"] = d.get("galat") or {}
    out["berkas"][nama] = rec
    konf = d.get("konfig")
    if konf:
        out["peta_tf"][konf] = {
            "entry_tf": d.get("entry_tf"),
            "context_tfs": d.get("context_tfs"),
            "trade": tot.get("trade"),
            "pf_bersih": tot.get("pf_bersih"),
            "pf_kotor": tot.get("pf_kotor"),
            "expectancy_r": tot.get("expectancy_r"),
            "biaya_per_trade": tot.get("biaya_per_trade"),
            "edge_kotor_per_trade": tot.get("edge_kotor_per_trade"),
            "rasio_biaya_atas_edge": (
                round(tot["biaya_per_trade"] / tot["edge_kotor_per_trade"], 4)
                if tot.get("biaya_per_trade") and tot.get("edge_kotor_per_trade")
                else None
            ),
            "breadth_pair_profit": d.get("breadth_pair_profit"),
            "terpotong": d.get("terpotong_batas_waktu"),
        }

with open(KELUARAN, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False, sort_keys=True)
print(json.dumps(out.get("peta_tf", {}), indent=1, ensure_ascii=False)[:6000])
print("keluaran: " + os.path.abspath(KELUARAN))
