#!/usr/bin/env python3
"""Probe: mengapa 'kandidat_per_strategi' kosong pada hasil backtest 95 pair?

Bukti yang sudah ada (hasil/bt95/bedah_runner.txt):
  ab95.py baris 412-415 SUDAH menjumlahkan kandidat_per_strategi dan
  menang_per_strategi dari `hasil.ringkas()`. Jadi agregatornya benar.

Maka sumbernya yang kosong. Dua hipotesis yang harus dipisahkan:
  H-A: Backtester.ringkas() tidak memuat kunci itu sama sekali.
  H-B: Kuncinya ada tetapi isinya kosong.

Probe ini menjalankan Backtester DAN Pipeline pada plane yang sama, lalu
membandingkan kunci ringkasan keduanya. Tidak ada logika strategi yang diubah;
ini murni pembacaan.
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
    print(json.dumps(out, indent=1, ensure_ascii=False, default=str)[:6000])


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
try:
    bt = ab.buat_backtester(plane, tfplan, True)
    hasil = bt.jalankan()
    r = hasil.ringkas() or {}
    trades = list(getattr(hasil, "trades", []) or [])
    per_id = {}
    for t in trades:
        sid = getattr(t, "strategy_id", None)
        per_id[sid] = per_id.get(sid, 0) + 1
    out["backtester"] = {
        "tipe_backtester": type(bt).__name__,
        "tipe_hasil": type(hasil).__name__,
        "kunci_ringkas": sorted(r),
        "ada_kunci_kandidat": "kandidat_per_strategi" in r,
        "ada_kunci_menang": "menang_per_strategi" in r,
        "kandidat_per_strategi": r.get("kandidat_per_strategi"),
        "menang_per_strategi": r.get("menang_per_strategi"),
        "bar_dievaluasi": r.get("bar_dievaluasi"),
        "jumlah_trade": len(trades),
        "trade_per_strategy_id": dict(
            sorted(per_id.items(), key=lambda kv: -kv[1])
        ),
        "atribut_hasil": sorted(
            a for a in dir(hasil) if not a.startswith("_")
        ),
        "atribut_backtester": sorted(
            a for a in dir(bt) if not a.startswith("_")
        ),
    }
except Exception:
    out["galat"]["backtester"] = traceback.format_exc()[-1500:]

# --- Pipeline sebagai pembanding pada plane yang SAMA ---
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
    if stat is None:
        for nama_attr in ("stat", "statistik", "stats"):
            kand = getattr(pipe, nama_attr, None)
            if hasattr(kand, "ringkas"):
                stat = kand
                out["catatan"].append("stat diambil dari pipe." + nama_attr)
                break
    rp = (stat.ringkas() if stat is not None else {}) or {}
    out["pipeline"] = {
        "tipe_kembalian": type(hp).__name__,
        "tipe_stat": type(stat).__name__ if stat is not None else None,
        "kunci_ringkas": sorted(rp),
        "ada_kunci_kandidat": "kandidat_per_strategi" in rp,
        "kandidat_per_strategi": rp.get("kandidat_per_strategi"),
        "menang_per_strategi": rp.get("menang_per_strategi"),
        "bar_dievaluasi": rp.get("bar_dievaluasi"),
        "entry": rp.get("entry"),
    }
except Exception:
    out["galat"]["pipeline"] = traceback.format_exc()[-1500:]

bt_kosong = not (out.get("backtester", {}).get("kandidat_per_strategi") or {})
pipe_isi = bool(out.get("pipeline", {}).get("kandidat_per_strategi") or {})
out["kesimpulan"] = {
    "backtester_kandidat_kosong": bt_kosong,
    "pipeline_kandidat_terisi": pipe_isi,
    "hipotesis_H_A_kunci_tidak_ada": out.get("backtester", {}).get(
        "ada_kunci_kandidat"
    )
    is False,
    "atribusi_masih_mungkin_lewat_trades": bool(
        out.get("backtester", {}).get("trade_per_strategy_id")
    ),
}

simpan()
