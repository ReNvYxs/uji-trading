#!/usr/bin/env python3
"""Teori v4 - UKUR SAJA. Tidak satu baris pun logika strategi diubah.

Dua pertanyaan dijawab dengan bukti, bukan asumsi.

S1. pivot_reversal memakai blok BERGULIR bar [-2n:-n] sebagai 'periode
    sebelumnya'. Pivot klasik (StockCharts ChartSchool, Investopedia,
    babypips) ditambatkan ke KALENDER: high/low/close hari sebelumnya, dan
    levelnya tetap sepanjang hari. Teori v3 sudah membuktikan levelnya beda
    (fraksi_identik 0.0 pada BTC 4h, selisih R1 p50 0.58 ATR). Yang BELUM
    diketahui: apakah beda itu penting secara ekonomi. Di sini kedua varian
    dibacktest berdampingan pada 95 pair. Registry hanya berisi SATU strategi,
    konstruksi Backtester identik, satu-satunya perbedaan = sumber pivot.

    Varian kalender adalah BAYANGAN milik probe. Dibuat lewat
    dataclasses.replace() atas spesifikasi asli, sehingga ambang, warmup,
    sl_atr, rr, porsi, horizon, kelompok DIJAMIN identik. Berkas modul tidak
    disentuh dan katalog tidak dimutasi.

S2. macd_rsi_trendbreak belum pernah terlihat trading di konfigurasi mana pun,
    dan level_bulat nol deteksi pada BTC 4h. Sensus ini menghitung verdict dan
    kode penolakan keduanya pada SELURUH 95 pair, supaya bisa dibedakan antara
    'langka' dan 'tidak pernah bisa terpenuhi'.

Catatan validitas: angka registry-terisolasi TIDAK sama dengan angka
registry-penuh. Backtester melompati bar selagi posisi terbuka, jadi okupansi
posisi berubah bila strategi lain dimatikan. Perbandingan yang sah di sini
adalah A lawan B, bukan A lawan hasil peta 95 pair.
"""
import dataclasses
import importlib.util
import inspect
import json
import os
import sys
import time
import traceback
from collections import defaultdict

import numpy as np

KELUAR = "hasil/teori4"
AB = os.environ.get("AB95_PATH", "klon_modul/scripts/ab95.py")
AKAR = os.environ.get("LUX_AKAR", "klon_modul")
BATAS = float(os.environ.get("LUX_BATAS_DETIK", "2400"))
MAKS_BAR_4H = int(os.environ.get("LUX_MAKS_BAR_4H", "1200"))
MAKS_BAR_1H = int(os.environ.get("LUX_MAKS_BAR_1H", "2000"))
MAKS_SIMBOL_1H = int(os.environ.get("LUX_MAKS_SIMBOL_1H", "30"))
MULAI = int(os.environ.get("LUX_MULAI", "300"))
MIN_SAMPEL = int(os.environ.get("LUX_MIN_SAMPEL", "200"))
MS_HARI = 86400000

t0 = time.time()
out = {"perintah": "teori4", "catatan": [], "galat": []}


def sisa():
    return BATAS - (time.time() - t0)


def simpan():
    os.makedirs(KELUAR, exist_ok=True)
    jalur = os.path.join(KELUAR, "TEORI4.json")
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

out["varian"] = aman("varian", ab.terapkan_varian)

from lux_modul.backtest import Backtester  # noqa: E402
from lux_modul.kontrak import (  # noqa: E402
    ARAH_LONG,
    ARAH_SHORT,
    HORIZON_INTRADAY,
    TFPlan,
)
from lux_modul.plugin import KATALOG_POLA, Deteksi, SpesifikasiPola  # noqa: E402
from lux_modul.strategi import Registry, StrategiPola, registry_dari  # noqa: E402
from lux_modul.strategi.level_harga import _bar_per_hari  # noqa: E402
from lux_modul.strategi.util import atr_kini, volume_breakout  # noqa: E402


def tanda(obj):
    try:
        return str(inspect.signature(obj))
    except Exception:
        return "?"


# Direkam permanen supaya probe berikutnya tidak perlu menebak bentuk argumen.
ttd = {
    "Backtester.__init__": tanda(Backtester.__init__),
    "Registry.__init__": tanda(Registry.__init__),
    "StrategiPola.__init__": tanda(StrategiPola.__init__),
    "ab.muat_plane": tanda(getattr(ab, "muat_plane", None)),
    "ab.daftar_simbol": tanda(getattr(ab, "daftar_simbol", None)),
    "ab.buat_backtester": tanda(getattr(ab, "buat_backtester", None)),
    "SpesifikasiPola_medan": [f.name for f in dataclasses.fields(SpesifikasiPola)]
    if dataclasses.is_dataclass(SpesifikasiPola)
    else "bukan dataclass",
}
out["tanda_tangan"] = ttd


# --------------------------------------------------- detektor pivot kalender
def _skala(x, lo, hi):
    if hi <= lo:
        return 0.0
    return float(max(0.0, min(1.0, (x - lo) / (hi - lo))))


HITUNG_KALENDER = defaultdict(int)


def _pivot_kalender(ctx):
    """Salinan setia _pivot_reversal; HANYA sumber pivot yang diganti.

    Modul: blok bergulir bar [-2n:-n].
    Di sini: hari kalender UTC terakhir yang sudah selesai sebelum hari bar
    berjalan. Tidak ada look-ahead: hanya bar dari hari yang lampau dipakai.
    """
    b = ctx.entry
    n = _bar_per_hari(b.tf)
    if len(b) < 2 * n + 5:
        return None

    h = np.asarray(b.high, dtype=float)
    l = np.asarray(b.low, dtype=float)
    c = np.asarray(b.close, dtype=float)
    ts = np.asarray(b.ts, dtype=np.int64)

    ekor = int(min(len(b), 8 * n + 10))
    hh = h[-ekor:]
    ll = l[-ekor:]
    cc = c[-ekor:]
    hari = ts[-ekor:] // MS_HARI
    hari_kini = int(hari[-1])
    lampau = hari[hari < hari_kini]
    if lampau.size == 0:
        HITUNG_KALENDER["tak_ada_hari_lampau"] += 1
        return None
    hari_lalu = int(lampau.max())
    pilih = hari == hari_lalu
    jumlah_bar_hari_lalu = int(pilih.sum())
    if jumlah_bar_hari_lalu < n:
        HITUNG_KALENDER["hari_lalu_tidak_penuh"] += 1
    if hari_lalu != hari_kini - 1:
        HITUNG_KALENDER["hari_lalu_bukan_kemarin"] += 1

    lalu_h = float(hh[pilih].max())
    lalu_l = float(ll[pilih].min())
    lalu_c = float(cc[pilih][-1])

    p = (lalu_h + lalu_l + lalu_c) / 3.0
    r1 = 2 * p - lalu_l
    s1 = 2 * p - lalu_h

    atr = atr_kini(ctx)
    tol = 0.4 * atr
    harga = float(c[-1])

    if h[-1] >= r1 - tol and harga < r1:
        arah = ARAH_SHORT
        invalid = float(max(h[-1], r1)) + 0.3 * atr
        level = r1
        sumbu = (h[-1] - max(harga, float(b.open[-1]))) / max(h[-1] - l[-1], 1e-12)
    elif l[-1] <= s1 + tol and harga > s1:
        arah = ARAH_LONG
        invalid = float(min(l[-1], s1)) - 0.3 * atr
        level = s1
        sumbu = (min(harga, float(b.open[-1])) - l[-1]) / max(h[-1] - l[-1], 1e-12)
    else:
        return None

    komponen = {
        "penolakan_sumbu": (_skala(float(sumbu), 0.2, 0.7), 1.0),
        "jarak_ke_pivot": (1.0 - _skala(abs(harga - p) / max(atr, 1e-12), 0.0, 6.0), 0.6),
        "konfirmasi_volume": (_skala(volume_breakout(ctx, 20), 0.8, 1.6), 0.7),
    }
    bukti = {
        "P": round(p, 10),
        "R1": round(r1, 10),
        "S1": round(s1, 10),
        "bar_hari_lalu": jumlah_bar_hari_lalu,
        "hari_lalu": hari_lalu,
    }
    return Deteksi(
        arah=arah,
        level=float(level),
        invalidation=float(invalid),
        komponen=komponen,
        bukti=bukti,
        fitur=("pivot_klasik",),
    )


SPEK_ASLI = KATALOG_POLA.get("pivot_reversal")
SPEK_KALENDER = None
if SPEK_ASLI is not None:
    try:
        SPEK_KALENDER = dataclasses.replace(SPEK_ASLI, detektor=_pivot_kalender)
        out["cara_bayangan"] = "dataclasses.replace"
    except Exception:
        SPEK_KALENDER = SpesifikasiPola(
            nama=SPEK_ASLI.nama,
            kelompok=SPEK_ASLI.kelompok,
            detektor=_pivot_kalender,
            ambang=SPEK_ASLI.ambang,
            warmup=SPEK_ASLI.warmup,
            konteks=SPEK_ASLI.konteks,
            horizon=SPEK_ASLI.horizon,
            sl_atr=SPEK_ASLI.sl_atr,
            rr=SPEK_ASLI.rr,
            porsi=SPEK_ASLI.porsi,
            deskripsi=SPEK_ASLI.deskripsi,
            sumber=SPEK_ASLI.sumber,
        )
        out["cara_bayangan"] = "konstruktor eksplisit"

# Bukti bahwa SATU-SATUNYA perbedaan adalah fungsi detektor.
beda_param = {}
if SPEK_ASLI is not None and SPEK_KALENDER is not None:
    for f in dataclasses.fields(SPEK_ASLI):
        va = getattr(SPEK_ASLI, f.name)
        vb = getattr(SPEK_KALENDER, f.name)
        if f.name == "detektor":
            beda_param[f.name] = "sengaja berbeda"
            continue
        beda_param[f.name] = "sama" if va == vb else ("BEDA " + str(va) + " vs " + str(vb))
out["parameter_bayangan"] = beda_param


def reg_asli():
    return registry_dari(["pivot_reversal"])


def reg_kalender():
    return Registry([StrategiPola(SPEK_KALENDER)])


# --------------------------------------------------------------- S1 backtest
def jalankan_arm(pembuat, simbol_list, tfplan, tfs, maks_bar, batas_arm):
    mulai_arm = time.time()
    rows = []
    per_simbol = {}
    gagal = {}
    bar_total = 0
    diproses = 0
    tolak_biaya = 0
    for simbol in simbol_list:
        if sisa() < 150 or (time.time() - mulai_arm) > batas_arm:
            break
        try:
            plane = ab.muat_plane(simbol, tfs, maks_bar)
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
            gagal[simbol] = str(e)[:180]
            continue
        diproses += 1
        r = hasil.ringkas() or {}
        bar_total += r.get("bar_dievaluasi", 0) or 0
        tolak_biaya += r.get("entry_ditolak_biaya", 0) or 0
        lokal = []
        for t in hasil.trades:
            rec = {
                "simbol": simbol,
                "arah": getattr(t, "arah", None),
                "ts_entry": getattr(t, "ts_entry", None),
                "alasan_keluar": getattr(t, "alasan_keluar", None),
                "pnl_bersih": float(getattr(t, "pnl_bersih", 0.0) or 0.0),
                "pnl_kotor": float(getattr(t, "pnl_kotor", 0.0) or 0.0),
                "biaya": float(getattr(t, "biaya", 0.0) or 0.0),
                "r_multiple": getattr(t, "r_multiple", None),
            }
            lokal.append(rec)
            rows.append(rec)
        per_simbol[simbol] = metrik(lokal)
    hasil_arm = {
        "simbol_diproses": diproses,
        "simbol_gagal": gagal,
        "bar_dievaluasi": bar_total,
        "entry_ditolak_biaya": tolak_biaya,
        "detik": round(time.time() - mulai_arm, 1),
    }
    return rows, per_simbol, hasil_arm


def dua_paruh(rows, batas_ts):
    if batas_ts is None:
        return {}, {}
    p1 = [r for r in rows if r.get("ts_entry") is not None and r["ts_entry"] < batas_ts]
    p2 = [r for r in rows if r.get("ts_entry") is not None and r["ts_entry"] >= batas_ts]
    return metrik(p1), metrik(p2)


def s1():
    entry_tf = "4h"
    tfs = (entry_tf,)
    tfplan = TFPlan(entry_tf=entry_tf, context_tfs=())
    simbol_list = list(ab.daftar_simbol(tfs))
    blok = {
        "konfig": "single_4h, registry berisi satu strategi saja",
        "entry_tf": entry_tf,
        "maks_bar": MAKS_BAR_4H,
        "simbol_tersedia": len(simbol_list),
    }
    baris_a, simb_a, meta_a = jalankan_arm(
        reg_asli, simbol_list, tfplan, tfs, MAKS_BAR_4H, 700.0
    )
    baris_b, simb_b, meta_b = jalankan_arm(
        reg_kalender, simbol_list, tfplan, tfs, MAKS_BAR_4H, 700.0
    )

    semua_ts = sorted(
        r["ts_entry"] for r in (baris_a + baris_b) if r.get("ts_entry") is not None
    )
    batas_ts = semua_ts[len(semua_ts) // 2] if semua_ts else None

    a1, a2 = dua_paruh(baris_a, batas_ts)
    b1, b2 = dua_paruh(baris_b, batas_ts)

    arm_a = dict(meta_a)
    arm_a["total"] = metrik(baris_a)
    arm_a["paruh_1"] = a1
    arm_a["paruh_2"] = a2
    arm_b = dict(meta_b)
    arm_b["total"] = metrik(baris_b)
    arm_b["paruh_1"] = b1
    arm_b["paruh_2"] = b2

    bersama = sorted(set(simb_a) & set(simb_b))
    delta = []
    menang_b = 0
    menang_a = 0
    seri = 0
    for s in bersama:
        pa = simb_a[s].get("pnl_bersih") or 0.0
        pb = simb_b[s].get("pnl_bersih") or 0.0
        delta.append(pb - pa)
        if pb > pa:
            menang_b += 1
        elif pa > pb:
            menang_a += 1
        else:
            seri += 1
    urut = sorted(
        ((s, bulat((simb_b[s].get("pnl_bersih") or 0.0) - (simb_a[s].get("pnl_bersih") or 0.0), 4)) for s in bersama),
        key=lambda kv: kv[1] if kv[1] is not None else 0.0,
    )
    banding = {
        "simbol_dibandingkan": len(bersama),
        "simbol_kalender_lebih_baik": menang_b,
        "simbol_modul_lebih_baik": menang_a,
        "simbol_seri": seri,
        "delta_pnl_per_simbol": ringkas_angka(delta),
        "delta_pnl_total": bulat(sum(delta), 4),
        "terburuk_5": urut[:5],
        "terbaik_5": urut[-5:][::-1],
    }
    blok["arm_a_modul_bergulir"] = arm_a
    blok["arm_b_kalender"] = arm_b
    blok["perbandingan_berpasangan"] = banding
    blok["batas_paruh_ts"] = batas_ts
    blok["hitung_kalender"] = dict(HITUNG_KALENDER)
    blok["peringatan"] = (
        "registry terisolasi: angka absolut tidak sebanding dengan peta 95 pair "
        "registry penuh, karena okupansi posisi berbeda. Yang sah adalah A vs B."
    )
    return blok


# ----------------------------------------------------------------- S2 sensus
def sensus(nama, entry_tf, ctx_tfs, ids, maks_bar, maks_simbol, batas_lokal):
    mulai_s = time.time()
    tfs = (entry_tf,) + tuple(ctx_tfs)
    tfplan = TFPlan(entry_tf=entry_tf, context_tfs=tuple(ctx_tfs))
    reg = registry_dari(list(ids))
    agg = {}
    for i in ids:
        agg[i] = {"verdict": 0, "lolos_ambang": 0, "tolak": defaultdict(int), "skor": []}
    contoh = {}
    simbol_list = list(ab.daftar_simbol(tfs))
    if maks_simbol:
        simbol_list = simbol_list[:maks_simbol]
    diproses = 0
    bar = 0
    ctx_gagal = 0
    gagal = {}
    simbol_dengan_verdict = defaultdict(set)
    for simbol in simbol_list:
        if sisa() < 90 or (time.time() - mulai_s) > batas_lokal:
            break
        try:
            plane = ab.muat_plane(simbol, tfs, maks_bar)
            entry = plane.bars(entry_tf)
        except Exception as e:
            gagal[simbol] = str(e)[:180]
            continue
        diproses += 1
        for i in range(MULAI, len(entry)):
            try:
                ctx = plane.konteks_pada(i, tfplan, HORIZON_INTRADAY)
            except Exception:
                ctx_gagal += 1
                continue
            if ctx is None:
                ctx_gagal += 1
                continue
            bar += 1
            h = reg.evaluasi_semua(ctx)
            for v in getattr(h, "verdicts", []) or []:
                sid = getattr(v, "strategy_id", None)
                if not contoh.get("verdict_atribut"):
                    contoh["verdict_atribut"] = sorted(
                        a for a in dir(v) if not a.startswith("_")
                    )
                if sid in agg:
                    agg[sid]["verdict"] += 1
                    simbol_dengan_verdict[sid].add(simbol)
                    sk = getattr(v, "skor", None)
                    if sk is not None:
                        agg[sid]["skor"].append(float(sk))
                    if getattr(v, "lolos_ambang", False):
                        agg[sid]["lolos_ambang"] += 1
            for p in getattr(h, "penolakan", []) or []:
                sid = getattr(p, "strategy_id", None)
                if not contoh.get("penolakan_atribut"):
                    contoh["penolakan_atribut"] = sorted(
                        a for a in dir(p) if not a.startswith("_")
                    )
                kode = str(getattr(p, "kode", p))
                kode = kode.replace("TOLAK_", "").lower()
                if sid in agg:
                    agg[sid]["tolak"][kode] += 1
    per = {}
    for i in ids:
        d = agg[i]
        per[i] = {
            "verdict": d["verdict"],
            "lolos_ambang": d["lolos_ambang"],
            "simbol_dengan_verdict": len(simbol_dengan_verdict.get(i, ())),
            "tolak": dict(sorted(d["tolak"].items())),
            "skor_ringkas": ringkas_angka(d["skor"]),
        }
    return {
        "konfig": nama,
        "entry_tf": entry_tf,
        "context_tfs": list(ctx_tfs),
        "maks_bar": maks_bar,
        "simbol_diproses": diproses,
        "simbol_gagal": gagal,
        "bar_dievaluasi": bar,
        "konteks_gagal": ctx_gagal,
        "introspeksi": contoh,
        "per_strategi": per,
        "detik": round(time.time() - mulai_s, 1),
    }


# ---------------------------------------------------------------------- main
out["s1_ab_pivot"] = aman("s1", s1)
simpan()

IDS = ["macd_rsi_trendbreak", "level_bulat", "pivot_reversal"]
out["s2_sensus_4h"] = aman(
    "sensus_4h",
    lambda: sensus("multi_4h_ctx1d", "4h", ("1d",), IDS, MAKS_BAR_4H, 0, 600.0),
)
simpan()

out["s2_sensus_1h"] = aman(
    "sensus_1h",
    lambda: sensus(
        "multi_1h_ctx4h", "1h", ("4h",), IDS, MAKS_BAR_1H, MAKS_SIMBOL_1H, 500.0
    ),
)

out["detik"] = round(time.time() - t0, 1)
simpan()

# Cetak RINGKAS saja. Pelajaran teori v3: mencetak seluruh isi membuat jejak
# dan berkas ringkas jadi duplikat persis dan boros dibaca.
s1b = out.get("s1_ab_pivot") or {}
arm_a = (s1b.get("arm_a_modul_bergulir") or {}).get("total") or {}
arm_b = (s1b.get("arm_b_kalender") or {}).get("total") or {}
pendek = {
    "detik": out.get("detik"),
    "galat": len(out.get("galat") or []),
    "cara_bayangan": out.get("cara_bayangan"),
    "parameter_bayangan_beda": [
        k for k, v in (out.get("parameter_bayangan") or {}).items() if str(v).startswith("BEDA")
    ],
    "a_modul": {
        "trade": arm_a.get("trade"),
        "pf": arm_a.get("pf_bersih"),
        "expR": arm_a.get("expectancy_r"),
        "pnl": arm_a.get("pnl_bersih"),
    },
    "b_kalender": {
        "trade": arm_b.get("trade"),
        "pf": arm_b.get("pf_bersih"),
        "expR": arm_b.get("expectancy_r"),
        "pnl": arm_b.get("pnl_bersih"),
    },
    "berpasangan": s1b.get("perbandingan_berpasangan"),
    "sensus_4h": (out.get("s2_sensus_4h") or {}).get("per_strategi"),
    "sensus_1h": (out.get("s2_sensus_1h") or {}).get("per_strategi"),
}
print(json.dumps(pendek, indent=1, ensure_ascii=False, default=str)[:6000])
for g in out.get("galat") or []:
    print("GALAT: " + g[:600])
print("keluaran: " + os.path.abspath(os.path.join(KELUAR, "TEORI4.json")))
