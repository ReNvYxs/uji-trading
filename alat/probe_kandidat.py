#!/usr/bin/env python3
"""Probe: mengapa 'kandidat_per_strategi' kosong pada hasil backtest 95 pair?

Bukti yang sudah ada:
  1. hasil/bt95/bedah_runner.txt -> ab95.py baris 412-415 SUDAH menjumlahkan
     kandidat_per_strategi dan menang_per_strategi dari `hasil.ringkas()`.
     Jadi agregatornya benar; sumbernya yang kosong.
  2. Putaran pertama probe ini -> Backtester.ringkas() TIDAK memuat kunci itu
     sama sekali (ada_kunci_kandidat=false), sedangkan Pipeline memuatnya.

Pertanyaan yang tinggal: Backtester punya atribut `.pipeline`. Kalau
StatistikJalan di dalamnya ikut terakumulasi selama jalankan(), atribusi
strategi bisa dipulihkan TANPA menjalankan Pipeline kedua kali (hemat ~2x
waktu komputasi untuk 95 pair). Probe ini memeriksa itu.

Tidak ada logika strategi yang diubah; ini murni pembacaan.
"""
import importlib.util
import json
import os
import sys
import traceback

AB = os.environ.get("AB95_PATH", "klon_modul/scripts/ab95.py")
KELUARAN = os.environ.get("LUX_KELUARAN", "hasil/bt95/probe_kandidat.json")

out = {"ab95": AB, "catatan": [], "galat": {}}


def simpan():
    induk = os.path.dirname(KELUARAN)
    if induk:
        os.makedirs(induk, exist_ok=True)
    with open(KELUARAN, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False, default=str)
    print(json.dumps(out, indent=1, ensure_ascii=False, default=str)[:7000])


try:
    spec = importlib.util.spec_from_file_location("ab95_mod", AB)
    ab = importlib.util.module_from_spec(spec)
    sys.modules["ab95_mod"] = ab
    spec.loader.exec_module(ab)
    out["catatan"].append("ab95 diimpor sebagai modul (main() tidak dijalankan)")
except Exception:
    out["galat"]["impor_ab95"] = traceback.format_exc()[-1500:]
    simpan()
    raise SystemExit(1)

try:
    konfig = os.environ.get("LUX_KONFIG", "single_15m")
    entry_tf, ctx = ab.KONFIG[konfig]
    tfs = (entry_tf,) + tuple(ctx)
    out["konfig"] = {
        "nama": konfig,
        "entry_tf": entry_tf,
        "context_tfs": list(ctx),
        "modal_awal": ab.MODAL_AWAL,
    }

    TFPlan = getattr(ab, "TFPlan", None)
    if TFPlan is None:
        from lux_modul.rencana_tf import TFPlan  # type: ignore

        out["catatan"].append("TFPlan diimpor dari lux_modul.rencana_tf")
    else:
        out["catatan"].append("TFPlan diambil dari namespace ab95")

    simbol_list = ab.daftar_simbol(tfs)
    out["simbol_tersedia"] = len(simbol_list)
    if not simbol_list:
        out["galat"]["simbol"] = "daftar_simbol kosong"
        simpan()
        raise SystemExit(2)
    simbol = simbol_list[0]
    out["simbol_diuji"] = simbol

    maks_bar = int(os.environ.get("LUX_MAKS_BAR", "1500"))
    plane = ab.muat_plane(simbol, tfs, maks_bar)
    tfplan = TFPlan(entry_tf=entry_tf, context_tfs=tuple(ctx))
    out["maks_bar"] = maks_bar
except SystemExit:
    raise
except Exception:
    out["galat"]["persiapan"] = traceback.format_exc()[-1500:]
    simpan()
    raise SystemExit(3)

# --- Backtester ---
bt = None
try:
    bt = ab.buat_backtester(plane, tfplan, True)
    hasil = bt.jalankan()
    r = hasil.ringkas() or {}
    trades = list(getattr(hasil, "trades", []) or [])
    per_id = {}
    menang_id = {}
    for t in trades:
        sid = getattr(t, "strategy_id", None)
        per_id[sid] = per_id.get(sid, 0) + 1
        if (getattr(t, "pnl_bersih", 0) or 0) > 0:
            menang_id[sid] = menang_id.get(sid, 0) + 1
    out["backtester"] = {
        "tipe_hasil": type(hasil).__name__,
        "kunci_ringkas": sorted(r),
        "ada_kunci_kandidat": "kandidat_per_strategi" in r,
        "kandidat_per_strategi": r.get("kandidat_per_strategi"),
        "bar_dievaluasi": r.get("bar_dievaluasi"),
        "jumlah_trade": len(trades),
        "trade_per_strategy_id": dict(sorted(per_id.items(), key=lambda kv: -kv[1])),
        "menang_per_strategy_id_dari_trades": dict(
            sorted(menang_id.items(), key=lambda kv: -kv[1])
        ),
    }
except Exception:
    out["galat"]["backtester"] = traceback.format_exc()[-1500:]

# --- KUNCI: apakah Pipeline internal Backtester ikut terakumulasi? ---
try:
    info = {"ada_atribut_pipeline": bt is not None and hasattr(bt, "pipeline")}
    if info["ada_atribut_pipeline"]:
        pi = bt.pipeline
        info["tipe"] = type(pi).__name__
        info["atribut"] = sorted(a for a in dir(pi) if not a.startswith("_"))
        for nama_attr in ("stat", "statistik", "stats", "statistik_jalan"):
            kand = getattr(pi, nama_attr, None)
            if hasattr(kand, "ringkas"):
                rr = kand.ringkas() or {}
                info["stat_diambil_dari"] = "pipeline." + nama_attr
                info["tipe_stat"] = type(kand).__name__
                info["bar_dievaluasi"] = rr.get("bar_dievaluasi")
                info["entry"] = rr.get("entry")
                info["kandidat_per_strategi"] = rr.get("kandidat_per_strategi")
                info["menang_per_strategi"] = rr.get("menang_per_strategi")
                break
        info["terakumulasi"] = bool(info.get("kandidat_per_strategi"))
    out["pipeline_internal_backtester"] = info
except Exception:
    out["galat"]["pipeline_internal"] = traceback.format_exc()[-1500:]

# --- Pipeline terpisah sebagai pembanding pada plane yang SAMA ---
try:
    pipe = ab.buat_pipeline(plane, tfplan, True)
    hp = pipe.jalankan_rentang()
    stat = None
    if isinstance(hp, tuple):
        for x in hp:
            if hasattr(x, "ringkas"):
                stat = x
    elif hasattr(hp, "ringkas"):
        stat = hp
    rp = (stat.ringkas() if stat is not None else {}) or {}
    out["pipeline_terpisah"] = {
        "tipe_stat": type(stat).__name__ if stat is not None else None,
        "kunci_ringkas": sorted(rp),
        "bar_dievaluasi": rp.get("bar_dievaluasi"),
        "entry": rp.get("entry"),
        "kandidat_per_strategi": rp.get("kandidat_per_strategi"),
    }
except Exception:
    out["galat"]["pipeline_terpisah"] = traceback.format_exc()[-1500:]

intern = out.get("pipeline_internal_backtester", {})
out["kesimpulan"] = {
    "backtester_ringkas_tanpa_kunci_kandidat": out.get("backtester", {}).get(
        "ada_kunci_kandidat"
    )
    is False,
    "atribusi_lewat_trades_tersedia": bool(
        out.get("backtester", {}).get("trade_per_strategy_id")
    ),
    "atribusi_murah_lewat_pipeline_internal": bool(intern.get("terakumulasi")),
    "perlu_pipeline_pass_kedua": not bool(intern.get("terakumulasi")),
}

simpan()
