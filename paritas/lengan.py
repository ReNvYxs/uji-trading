#!/usr/bin/env python3
"""Satu lengan uji paritas modul.

Dijalankan sebagai proses TERPISAH. Alasannya teknis dan penting: dua pohon
lux_modul yang berbeda tidak mungkin hidup berdampingan dalam satu proses
Python karena sys.modules akan menyimpan yang pertama diimpor. Menjalankan
keduanya dalam satu proses akan menghasilkan paritas palsu, sebab lengan kedua
sebenarnya memakai kode lengan pertama.

Lengan ini menjalankan backtest single_4h pada seluruh simbol dataset memakai
registry bawaan, lalu menulis sidik jari trade level-per-level. Sidik jari itu
yang membuat paritas dapat DIBUKTIKAN, bukan sekadar agregatnya yang kebetulan
sama.
"""
import hashlib
import importlib.util
import json
import os
import sys
import time
import traceback
from collections import defaultdict

AKAR = os.environ.get("PAR_AKAR", "klon_modul")
LABEL = os.environ.get("PAR_LABEL", "?")
KELUARAN = os.environ.get("PAR_KELUARAN", "hasil/paritas/lengan.json")
MAKS_BAR = int(os.environ.get("LUX_MAKS_BAR_4H", "1200"))
BATAS = float(os.environ.get("LUX_BATAS_DETIK", "2400"))
ENTRY_TF = os.environ.get("PAR_TF", "4h")

t0 = time.time()
out = {
    "label": LABEL,
    "akar": AKAR,
    "tf": ENTRY_TF,
    "maks_bar": MAKS_BAR,
    "galat": [],
}

KUNCI_JUMLAH = [
    "bar_dievaluasi",
    "entry_batal_gap",
    "entry_ditolak_biaya",
    "entry_ditolak_sizing",
    "jumlah_trade",
    "kalah",
    "menang",
]


def bulat(x, n=6):
    if x is None:
        return None
    try:
        f = float(x)
    except Exception:
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return round(f, n)


def tulis():
    d = os.path.dirname(KELUARAN)
    if d:
        os.makedirs(d, exist_ok=True)
    fh = open(KELUARAN, "w", encoding="utf-8")
    json.dump(out, fh, indent=1, ensure_ascii=False, sort_keys=True, default=str)
    fh.close()


def inventaris(akar):
    basis = os.path.join(akar, "lux_modul")
    peta = {}
    if not os.path.isdir(basis):
        return peta
    for dirpath, dirnames, filenames in os.walk(basis):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            penuh = os.path.join(dirpath, fn)
            rel = os.path.relpath(penuh, basis).replace(os.sep, "/")
            fh = open(penuh, "rb")
            isi = fh.read()
            fh.close()
            peta[rel] = hashlib.md5(isi).hexdigest()
    return peta


def ringkas_baris(rows):
    n = len(rows)
    if n == 0:
        return {"trade": 0, "menang": 0, "pnl_bersih": 0.0, "pnl_kotor": 0.0, "biaya": 0.0, "pf_bersih": None}
    pnl = sum(r["pnl_bersih"] for r in rows)
    kotor = sum(r["pnl_kotor"] for r in rows)
    biaya = sum(r["biaya"] for r in rows)
    menang = sum(1 for r in rows if r["pnl_bersih"] > 0)
    laba = sum(r["pnl_bersih"] for r in rows if r["pnl_bersih"] > 0)
    rugi = -sum(r["pnl_bersih"] for r in rows if r["pnl_bersih"] < 0)
    return {
        "trade": n,
        "menang": menang,
        "pnl_bersih": bulat(pnl),
        "pnl_kotor": bulat(kotor),
        "biaya": bulat(biaya),
        "pf_bersih": bulat(laba / rugi, 6) if rugi > 0 else None,
    }


out["inventaris"] = inventaris(AKAR)
out["jumlah_berkas_py"] = len(out["inventaris"])
tulis()

sys.path.insert(0, os.path.abspath(AKAR))
AB = os.environ.get("AB95_PATH") or os.path.join(AKAR, "scripts", "ab95.py")
out["ab95"] = AB
spec = importlib.util.spec_from_file_location("ab95_mod", AB)
ab = importlib.util.module_from_spec(spec)
sys.modules["ab95_mod"] = ab
spec.loader.exec_module(ab)

try:
    out["varian_modul"] = ab.terapkan_varian()
except Exception:
    out["galat"].append("terapkan_varian: " + traceback.format_exc()[-400:])

from lux_modul.backtest import Backtester  # noqa: E402
from lux_modul.kontrak import HORIZON_INTRADAY, TFPlan  # noqa: E402
from lux_modul.strategi import registry_bawaan  # noqa: E402

try:
    import lux_modul as _lm

    out["lux_modul_file"] = str(getattr(_lm, "__file__", "?"))
except Exception:
    out["lux_modul_file"] = "?"

reg0 = registry_bawaan()
peta0 = getattr(reg0, "_peta", None)
if isinstance(peta0, dict) and peta0:
    out["registry_id"] = sorted(str(k) for k in peta0.keys())
else:
    out["registry_id"] = []
out["modal_awal"] = bulat(getattr(ab, "MODAL_AWAL", None), 4)

TFS = (ENTRY_TF,)
TFPLAN = TFPlan(entry_tf=ENTRY_TF, context_tfs=())
SIMBOL = sorted(str(s) for s in ab.daftar_simbol(TFS))
out["simbol_tersedia"] = len(SIMBOL)
tulis()

sidik = hashlib.md5()
semua = []
per_simbol = {}
per_strategi = defaultdict(list)
mesin = {}
for k in KUNCI_JUMLAH:
    mesin[k] = 0
diproses = []
gagal = {}
bar_tersedia = 0

for simbol in SIMBOL:
    if (time.time() - t0) > BATAS:
        out["galat"].append("waktu habis sebelum " + simbol)
        break
    try:
        plane = ab.muat_plane(simbol, TFS, MAKS_BAR)
    except Exception as e:
        gagal[simbol] = ("muat: " + str(e))[:180]
        continue
    try:
        n_bar = int(len(plane.bars(ENTRY_TF)))
    except Exception:
        n_bar = 0
    try:
        bt = Backtester(
            plane,
            TFPLAN,
            horizon=HORIZON_INTRADAY,
            registry=registry_bawaan(),
            balance_awal=ab.MODAL_AWAL,
            saring_biaya=True,
        )
        hasil = bt.jalankan()
    except Exception as e:
        gagal[simbol] = ("jalankan: " + str(e))[:180]
        continue
    diproses.append(simbol)
    bar_tersedia += n_bar
    try:
        r = hasil.ringkas() or {}
    except Exception:
        r = {}
    for k in KUNCI_JUMLAH:
        v = r.get(k)
        if isinstance(v, (int, float)):
            mesin[k] += int(v)
    rows = []
    for t in hasil.trades:
        sid = str(getattr(t, "strategy_id", None))
        arah = str(getattr(t, "arah", None))
        te = getattr(t, "ts_entry", None)
        tk = getattr(t, "ts_keluar", None)
        alasan = str(getattr(t, "alasan_keluar", None))
        pnl = float(getattr(t, "pnl_bersih", 0.0) or 0.0)
        kotor = float(getattr(t, "pnl_kotor", 0.0) or 0.0)
        biaya = float(getattr(t, "biaya", 0.0) or 0.0)
        rows.append(
            {
                "simbol": simbol,
                "strategy_id": sid,
                "arah": arah,
                "ts_entry": te,
                "ts_keluar": tk,
                "alasan_keluar": alasan,
                "pnl_bersih": pnl,
                "pnl_kotor": kotor,
                "biaya": biaya,
            }
        )
        potong = "|".join(
            [
                simbol,
                sid,
                arah,
                str(te),
                str(tk),
                alasan,
                format(pnl, ".6f"),
                format(kotor, ".6f"),
                format(biaya, ".6f"),
            ]
        )
        sidik.update(potong.encode("utf-8"))
        sidik.update(b"\n")
    for baris in rows:
        per_strategi[baris["strategy_id"]].append(baris)
    semua.extend(rows)
    per_simbol[simbol] = ringkas_baris(rows)

out["simbol_diproses"] = diproses
out["simbol_gagal"] = gagal
out["bar_tersedia"] = bar_tersedia
out["mesin"] = mesin
out["total"] = ringkas_baris(semua)
out["per_simbol"] = per_simbol
ps = {}
for k in per_strategi:
    ps[k] = ringkas_baris(per_strategi[k])
out["per_strategi"] = ps
out["sidik_trade"] = sidik.hexdigest()
out["detik"] = round(time.time() - t0, 1)
tulis()

print("lengan=" + LABEL)
print("akar=" + AKAR)
print("lux_modul_file=" + str(out.get("lux_modul_file")))
print("berkas_py=" + str(out["jumlah_berkas_py"]))
print("registry=" + str(len(out["registry_id"])))
print("simbol_diproses=" + str(len(diproses)))
print("bar_tersedia=" + str(bar_tersedia))
print("trade=" + str(out["total"].get("trade")))
print("pnl_bersih=" + str(out["total"].get("pnl_bersih")))
print("sidik_trade=" + out["sidik_trade"])
print("detik=" + str(out["detik"]))
for g in out["galat"]:
    print("GALAT: " + g[:400])
