#!/usr/bin/env python3
"""Teori v5 - UKUR SAJA. Tidak satu baris pun logika strategi diubah.

Latar belakang. Peta TF menunjukkan single_4h adalah satu-satunya konfigurasi
net positif, dan di dalamnya hanya pivot_reversal yang lolos gerbang kelayakan.
Teori v4 lalu mengukur pivot_reversal SENDIRIAN pada 95 pair yang sama dan
hasilnya justru RUGI (PF 0.9545). Dua angka itu berasal dari run berbeda,
jadi belum boleh disimpulkan. Probe ini membuat perbandingannya terkontrol.

Pertanyaan yang dijawab dengan bukti.

P1. Apakah arbiter/okupansi posisi yang memilih sinyal terbaik itu menambah
    nilai? Bandingkan tiap strategi saat SENDIRIAN lawan saat bersaing di
    registry penuh, pada simbol, bar, dan konstruksi Backtester yang identik.

P2. Apakah membuang strategi yang selalu rugi benar-benar memperbaiki hasil?
    level_bulat negatif di enam konfigurasi TF, vp_tepi_value_area negatif di
    empat. Leave-one-out mengukur efek membuangnya, termasuk efek kaskade ke
    strategi lain yang mewarisi slot posisinya.

P3. Apakah daftar putih naif aman? Ambil strategi yang PnL-nya positif di
    baseline, jalankan hanya mereka, lalu lihat apakah totalnya membaik atau
    justru runtuh. Ini menguji langsung ide 'jalankan yang menang saja'.

Desain agar sah dibandingkan. Plane dimuat SEKALI per simbol lalu dipakai
ulang oleh semua varian, sehingga data, cache fitur, dan urutan bar identik.
Satu simbol hanya dihitung bila SELURUH varian berhasil, sehingga perbandingan
selalu berpasangan. Bila waktu habis, loop berhenti di batas simbol, bukan di
tengah varian, jadi himpunan simbol tetap sama untuk semua varian.
"""
import importlib.util
import inspect
import json
import os
import sys
import time
import traceback
from collections import defaultdict

KELUAR = "hasil/teori5"
AB = os.environ.get("AB95_PATH", "klon_modul/scripts/ab95.py")
AKAR = os.environ.get("LUX_AKAR", "klon_modul")
BATAS = float(os.environ.get("LUX_BATAS_DETIK", "2700"))
MAKS_BAR = int(os.environ.get("LUX_MAKS_BAR_4H", "1200"))
MIN_SAMPEL = int(os.environ.get("LUX_MIN_SAMPEL", "200"))
BATAS_RUN = float(os.environ.get("LUX_BATAS_RUN", "1500"))

t0 = time.time()
out = {"perintah": "teori5", "catatan": [], "galat": []}


def sisa():
    return BATAS - (time.time() - t0)


def simpan():
    os.makedirs(KELUAR, exist_ok=True)
    jalur = os.path.join(KELUAR, "TEORI5.json")
    fh = open(jalur, "w", encoding="utf-8")
    json.dump(out, fh, indent=1, ensure_ascii=False, sort_keys=True, default=str)
    fh.close()


def aman(nama, fn):
    try:
        return fn()
    except Exception:
        out["galat"].append(nama + ": " + traceback.format_exc()[-900:])
        return None


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


def pf(laba, rugi):
    if rugi and rugi > 0:
        return bulat(laba / rugi, 4)
    return None


def ringkas_angka(nilai):
    a = sorted(float(x) for x in nilai if x is not None)
    if not a:
        return {"n": 0}

    def q(p):
        if len(a) == 1:
            return a[0]
        k = (len(a) - 1) * p
        lo = int(k)
        hi = min(lo + 1, len(a) - 1)
        return a[lo] + (a[hi] - a[lo]) * (k - lo)

    return {
        "n": len(a),
        "min": bulat(a[0]),
        "p50": bulat(q(0.5)),
        "p90": bulat(q(0.9)),
        "maks": bulat(a[-1]),
        "rata": bulat(sum(a) / len(a)),
    }


def metrik(rows):
    n = len(rows)
    if n == 0:
        return {"trade": 0}
    pnl = [r["pnl_bersih"] for r in rows]
    kotor = [r["pnl_kotor"] for r in rows]
    biaya = [r["biaya"] for r in rows]
    rr = [r["r_multiple"] for r in rows if isinstance(r.get("r_multiple"), (int, float))]
    menang = sum(1 for x in pnl if x > 0)
    laba_b = sum(x for x in pnl if x > 0)
    rugi_b = -sum(x for x in pnl if x < 0)
    laba_k = sum(x for x in kotor if x > 0)
    rugi_k = -sum(x for x in kotor if x < 0)
    m = {
        "trade": n,
        "menang": menang,
        "win_rate": bulat(menang / n, 4),
        "pnl_bersih": bulat(sum(pnl), 4),
        "pnl_kotor": bulat(sum(kotor), 4),
        "biaya": bulat(sum(biaya), 4),
        "pf_bersih": pf(laba_b, rugi_b),
        "pf_kotor": pf(laba_k, rugi_k),
        "biaya_per_trade": bulat(sum(biaya) / n, 4),
        "pnl_bersih_per_trade": bulat(sum(pnl) / n, 4),
        "sampel_cukup": bool(n >= MIN_SAMPEL),
    }
    if rr:
        menang_r = [x for x in rr if x > 0]
        kalah_r = [x for x in rr if x <= 0]
        m["expectancy_r"] = bulat(sum(rr) / len(rr), 4)
        m["r_menang"] = bulat(sum(menang_r) / max(1, len(menang_r)), 4)
        m["r_kalah"] = bulat(sum(kalah_r) / max(1, len(kalah_r)), 4)
    return m


# ---------------------------------------------------------------- muat ab95
spec = importlib.util.spec_from_file_location("ab95_mod", AB)
ab = importlib.util.module_from_spec(spec)
sys.modules["ab95_mod"] = ab
spec.loader.exec_module(ab)
sys.path.insert(0, os.path.abspath(AKAR))

out["varian_modul"] = aman("varian", ab.terapkan_varian)

from lux_modul.backtest import Backtester  # noqa: E402
from lux_modul.kontrak import HORIZON_INTRADAY, TFPlan  # noqa: E402
from lux_modul.strategi import Registry, registry_dari  # noqa: E402

try:
    from lux_modul.strategi import registry_bawaan  # noqa: E402
except Exception:
    registry_bawaan = None


def tanda(obj):
    try:
        return str(inspect.signature(obj))
    except Exception:
        return "?"


out["tanda_tangan"] = {
    "Backtester.__init__": tanda(Backtester.__init__),
    "Registry.__init__": tanda(Registry.__init__),
    "registry_dari": tanda(registry_dari),
    "registry_bawaan": tanda(registry_bawaan) if registry_bawaan else "tidak ada",
    "ab.muat_plane": tanda(getattr(ab, "muat_plane", None)),
    "ab.daftar_simbol": tanda(getattr(ab, "daftar_simbol", None)),
}

NAMA_DIKETAHUI = [
    "breaker_block",
    "breakout_volume",
    "cup_and_handle",
    "donchian_breakout",
    "double_bottom",
    "double_top",
    "ema_bounce_200",
    "fib_golden_pocket",
    "fvg_fill",
    "head_shoulders",
    "ict_liquidity_sweep",
    "keltner_reversi",
    "level_bulat",
    "macd_rsi_trendbreak",
    "market_structure_shift",
    "order_block_retest",
    "pivot_reversal",
    "rsi_divergence",
    "smc_ob_fvg",
    "squeeze_breakout",
    "supertrend_flip",
    "triangle_breakout",
    "vp_tepi_value_area",
    "vwap_reclaim",
    "vwap_reversi_pita",
    "wedge_breakout",
]


def nama_registry(reg):
    p = getattr(reg, "_peta", None)
    if isinstance(p, dict) and p:
        return sorted(str(k) for k in p.keys()), "_peta"
    d = getattr(reg, "daftar", None)
    if callable(d):
        try:
            d = d()
        except Exception:
            d = None
    if isinstance(d, dict) and d:
        return sorted(str(k) for k in d.keys()), "daftar_dict"
    kumpul = []
    sumber = None
    if isinstance(d, (list, tuple)) and d:
        kumpul = list(d)
        sumber = "daftar_list"
    else:
        try:
            kumpul = list(reg.semua())
            sumber = "semua()"
        except Exception:
            kumpul = []
    nama = []
    for x in kumpul:
        n = getattr(x, "nama", None) or getattr(x, "id", None)
        if n is None:
            sp = getattr(x, "spek", None)
            n = getattr(sp, "nama", None)
        if n:
            nama.append(str(n))
    if nama:
        return sorted(set(nama)), sumber
    return [], sumber or "gagal"


NAMA = []
JALUR = "registry_bawaan tidak ada"
if registry_bawaan is not None:
    reg_awal = aman("registry_bawaan", registry_bawaan)
    if reg_awal is not None:
        NAMA, JALUR = nama_registry(reg_awal)
CADANGAN = False
if not NAMA:
    NAMA = list(NAMA_DIKETAHUI)
    CADANGAN = True

out["registry"] = {
    "jumlah": len(NAMA),
    "jalur_penemuan_nama": JALUR,
    "pakai_daftar_cadangan": CADANGAN,
    "selisih_vs_daftar_diketahui": sorted(set(NAMA) ^ set(NAMA_DIKETAHUI)),
    "nama": NAMA,
}


def buat_pembuat(nama_list):
    beku = list(nama_list)

    def f():
        return registry_dari(list(beku))

    return f


PEMBUAT_DASAR = registry_bawaan if registry_bawaan is not None else buat_pembuat(NAMA)
BUANG_1 = "level_bulat"
BUANG_2 = "vp_tepi_value_area"
ISOLASI = ["pivot_reversal", "level_bulat", "vwap_reclaim", "vp_tepi_value_area"]


# --------------------------------------------------------------- satu lintas
def lintas(varian_list, simbol_list, tfplan, tfs, batas_lokal):
    mulai = time.time()
    baris = {}
    per_simbol = {}
    for nama, _ in varian_list:
        baris[nama] = []
        per_simbol[nama] = {}
    gagal = {}
    diproses = []
    for simbol in simbol_list:
        if sisa() < 200 or (time.time() - mulai) > batas_lokal:
            break
        try:
            plane = ab.muat_plane(simbol, tfs, MAKS_BAR)
        except Exception as e:
            gagal[simbol] = ("muat: " + str(e))[:180]
            continue
        lokal = {}
        ok = True
        for nama, pembuat in varian_list:
            try:
                bt = Backtester(
                    plane,
                    tfplan,
                    horizon=HORIZON_INTRADAY,
                    registry=pembuat(),
                    balance_awal=ab.MODAL_AWAL,
                    saring_biaya=True,
                )
                hasil = bt.jalankan()
            except Exception as e:
                gagal[simbol + " / " + nama] = str(e)[:180]
                ok = False
                break
            rows = []
            for t in hasil.trades:
                rows.append(
                    {
                        "simbol": simbol,
                        "strategy_id": getattr(t, "strategy_id", None),
                        "arah": getattr(t, "arah", None),
                        "ts_entry": getattr(t, "ts_entry", None),
                        "alasan_keluar": getattr(t, "alasan_keluar", None),
                        "pnl_bersih": float(getattr(t, "pnl_bersih", 0.0) or 0.0),
                        "pnl_kotor": float(getattr(t, "pnl_kotor", 0.0) or 0.0),
                        "biaya": float(getattr(t, "biaya", 0.0) or 0.0),
                        "r_multiple": getattr(t, "r_multiple", None),
                    }
                )
            lokal[nama] = rows
        if not ok:
            continue
        diproses.append(simbol)
        for nama in lokal:
            baris[nama].extend(lokal[nama])
            per_simbol[nama][simbol] = metrik(lokal[nama])
    meta = {
        "simbol_diproses": len(diproses),
        "simbol_gagal": gagal,
        "detik": round(time.time() - mulai, 1),
    }
    return baris, per_simbol, diproses, meta


def dua_paruh(rows, batas_ts):
    if batas_ts is None:
        return {}, {}
    p1 = [r for r in rows if r.get("ts_entry") is not None and r["ts_entry"] < batas_ts]
    p2 = [r for r in rows if r.get("ts_entry") is not None and r["ts_entry"] >= batas_ts]
    return metrik(p1), metrik(p2)


def bagi_strategi(rows, batas_ts=None):
    per = defaultdict(list)
    for r in rows:
        per[str(r.get("strategy_id"))].append(r)
    hasil = {}
    for k in per:
        m = metrik(per[k])
        if batas_ts is not None:
            a, b = dua_paruh(per[k], batas_ts)
            m["p1_pnl"] = a.get("pnl_bersih")
            m["p2_pnl"] = b.get("pnl_bersih")
        hasil[k] = m
    return hasil


KUNCI_DELTA = ["trade", "pnl_bersih", "pf_bersih", "expectancy_r", "biaya", "win_rate"]


def delta(dasar, lain):
    d = {}
    for k in KUNCI_DELTA:
        a = dasar.get(k)
        b = lain.get(k)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            d[k] = bulat(b - a, 6)
        else:
            d[k] = None
    return d


def banding_simbol(ps_dasar, ps_lain):
    bersama = sorted(set(ps_dasar) & set(ps_lain))
    delta_list = []
    lebih_baik = 0
    lebih_buruk = 0
    seri = 0
    pasangan = []
    for s in bersama:
        a = ps_dasar[s].get("pnl_bersih") or 0.0
        b = ps_lain[s].get("pnl_bersih") or 0.0
        delta_list.append(b - a)
        pasangan.append((s, bulat(b - a, 4)))
        if b > a:
            lebih_baik += 1
        elif a > b:
            lebih_buruk += 1
        else:
            seri += 1
    pasangan.sort(key=lambda kv: kv[1] if kv[1] is not None else 0.0)
    return {
        "simbol_dibandingkan": len(bersama),
        "simbol_membaik": lebih_baik,
        "simbol_memburuk": lebih_buruk,
        "simbol_seri": seri,
        "delta_pnl_per_simbol": ringkas_angka(delta_list),
        "delta_pnl_total": bulat(sum(delta_list), 4),
        "terburuk_5": pasangan[:5],
        "terbaik_5": pasangan[-5:][::-1],
    }


# --------------------------------------------------------------------- utama
ENTRY_TF = "4h"
TFS = (ENTRY_TF,)
TFPLAN = TFPlan(entry_tf=ENTRY_TF, context_tfs=())
SIMBOL = list(ab.daftar_simbol(TFS))
out["simbol_tersedia"] = len(SIMBOL)
out["konfig"] = "single_4h, maks_bar " + str(MAKS_BAR) + ", saring_biaya True"

TANPA_1 = [n for n in NAMA if n != BUANG_1]
TANPA_2 = [n for n in NAMA if n != BUANG_2]
TANPA_DUA = [n for n in NAMA if n not in (BUANG_1, BUANG_2)]

VARIAN = [
    ("dasar", PEMBUAT_DASAR),
    ("tanpa_" + BUANG_1, buat_pembuat(TANPA_1)),
    ("tanpa_" + BUANG_2, buat_pembuat(TANPA_2)),
    ("tanpa_dua_terburuk", buat_pembuat(TANPA_DUA)),
]
for sid in ISOLASI:
    if sid in NAMA:
        VARIAN.append(("isolasi_" + sid, buat_pembuat([sid])))

out["varian_lintas1"] = [v[0] for v in VARIAN]

BARIS, PS, DIPROSES, META = lintas(VARIAN, SIMBOL, TFPLAN, TFS, BATAS_RUN)
out["lintas1"] = META
simpan()

ts_dasar = sorted(
    r["ts_entry"] for r in BARIS.get("dasar", []) if r.get("ts_entry") is not None
)
BATAS_TS = ts_dasar[len(ts_dasar) // 2] if ts_dasar else None
out["batas_paruh_ts"] = BATAS_TS

blok = {}
for nama, _ in VARIAN:
    rows = BARIS[nama]
    b = {"total": metrik(rows)}
    a1, a2 = dua_paruh(rows, BATAS_TS)
    b["paruh_1_pnl"] = a1.get("pnl_bersih")
    b["paruh_2_pnl"] = a2.get("pnl_bersih")
    b["per_strategi"] = bagi_strategi(rows, BATAS_TS)
    blok[nama] = b

DASAR_TOTAL = blok["dasar"]["total"]
DASAR_PER = blok["dasar"]["per_strategi"]

for nama in blok:
    if nama == "dasar":
        continue
    blok[nama]["delta_vs_dasar"] = delta(DASAR_TOTAL, blok[nama]["total"])
    blok[nama]["berpasangan_vs_dasar"] = banding_simbol(PS["dasar"], PS[nama])

out["varian"] = blok
simpan()

# P1. Nilai seleksi arbiter: sendirian lawan bersaing.
seleksi = {}
for sid in ISOLASI:
    kunci = "isolasi_" + sid
    if kunci not in blok:
        continue
    iso = blok[kunci]["total"]
    kom = DASAR_PER.get(sid) or {"trade": 0}
    ti = iso.get("trade") or 0
    tk = kom.get("trade") or 0
    seleksi[sid] = {
        "trade_sendirian": ti,
        "trade_dalam_kompetisi": tk,
        "rasio_penekanan": bulat(ti / tk, 4) if tk else None,
        "pf_sendirian": iso.get("pf_bersih"),
        "pf_dalam_kompetisi": kom.get("pf_bersih"),
        "expR_sendirian": iso.get("expectancy_r"),
        "expR_dalam_kompetisi": kom.get("expectancy_r"),
        "pnl_sendirian": iso.get("pnl_bersih"),
        "pnl_dalam_kompetisi": kom.get("pnl_bersih"),
    }
out["p1_nilai_seleksi"] = seleksi
simpan()

# P3. Daftar putih naif dari strategi yang PnL-nya positif di baseline.
PUTIH = sorted(
    k
    for k in DASAR_PER
    if k in NAMA and (DASAR_PER[k].get("pnl_bersih") or 0.0) > 0.0
)
out["daftar_putih"] = {
    "anggota": PUTIH,
    "jumlah": len(PUTIH),
    "dasar_pemilihan": "pnl_bersih positif pada varian dasar, lintas 1",
}

if PUTIH and len(PUTIH) < len(NAMA) and sisa() > 300:
    V2 = [("daftar_putih", buat_pembuat(PUTIH))]
    B2, PS2, DIP2, META2 = lintas(V2, DIPROSES, TFPLAN, TFS, min(BATAS_RUN, sisa() - 200))
    rows2 = B2["daftar_putih"]
    b2 = {"total": metrik(rows2)}
    c1, c2 = dua_paruh(rows2, BATAS_TS)
    b2["paruh_1_pnl"] = c1.get("pnl_bersih")
    b2["paruh_2_pnl"] = c2.get("pnl_bersih")
    b2["per_strategi"] = bagi_strategi(rows2, BATAS_TS)
    b2["delta_vs_dasar"] = delta(DASAR_TOTAL, b2["total"])
    b2["berpasangan_vs_dasar"] = banding_simbol(PS["dasar"], PS2["daftar_putih"])
    b2["meta"] = META2
    b2["simbol_sama_dengan_lintas1"] = bool(len(DIP2) == len(DIPROSES))
    out["p3_daftar_putih"] = b2
else:
    out["catatan"].append("daftar putih dilewati: kosong, sama dengan penuh, atau waktu habis")

out["detik"] = round(time.time() - t0, 1)
simpan()

# Cetak RINGKAS saja supaya jejak tidak menjadi duplikat berkas bukti.
ringkas = {
    "detik": out.get("detik"),
    "galat": len(out.get("galat") or []),
    "simbol_diproses": META.get("simbol_diproses"),
    "registry_jumlah": len(NAMA),
    "registry_jalur": JALUR,
    "selisih_nama": out["registry"]["selisih_vs_daftar_diketahui"],
    "total": {},
    "delta_vs_dasar": {},
    "p1_nilai_seleksi": seleksi,
    "daftar_putih": out["daftar_putih"],
}
for nama in blok:
    tt = blok[nama]["total"]
    ringkas["total"][nama] = {
        "trade": tt.get("trade"),
        "pf": tt.get("pf_bersih"),
        "expR": tt.get("expectancy_r"),
        "pnl": tt.get("pnl_bersih"),
        "p1": blok[nama].get("paruh_1_pnl"),
        "p2": blok[nama].get("paruh_2_pnl"),
    }
    if nama != "dasar":
        bp = blok[nama].get("berpasangan_vs_dasar") or {}
        ringkas["delta_vs_dasar"][nama] = {
            "delta": blok[nama].get("delta_vs_dasar"),
            "simbol_membaik": bp.get("simbol_membaik"),
            "simbol_memburuk": bp.get("simbol_memburuk"),
        }
p3 = out.get("p3_daftar_putih")
if p3:
    tt = p3["total"]
    ringkas["total"]["daftar_putih"] = {
        "trade": tt.get("trade"),
        "pf": tt.get("pf_bersih"),
        "expR": tt.get("expectancy_r"),
        "pnl": tt.get("pnl_bersih"),
        "p1": p3.get("paruh_1_pnl"),
        "p2": p3.get("paruh_2_pnl"),
    }
    bp = p3.get("berpasangan_vs_dasar") or {}
    ringkas["delta_vs_dasar"]["daftar_putih"] = {
        "delta": p3.get("delta_vs_dasar"),
        "simbol_membaik": bp.get("simbol_membaik"),
        "simbol_memburuk": bp.get("simbol_memburuk"),
    }

print(json.dumps(ringkas, indent=1, ensure_ascii=False, default=str)[:7000])
for g in out.get("galat") or []:
    print("GALAT: " + g[:600])
print("keluaran: " + os.path.abspath(os.path.join(KELUAR, "TEORI5.json")))
