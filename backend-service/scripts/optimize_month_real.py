#!/usr/bin/env python3
"""
Exit / frequency variants of the momentum engine on last month's REAL Upstox data (logs/realdata). The slow part
(the engine's analysis over every minute) runs once per underlying and is cached; each variant only re-runs the
trade management. Every variant is also scored on each HALF of the month separately: a change that only helps one
half is curve-fitting to this one rally, not an improvement.

  PYTHONPATH=. python scripts/optimize_month_real.py
"""
from __future__ import annotations

import pickle
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest_day as bd  # noqa: E402
import backtest_month_real as bm  # noqa: E402
import backtest_setups as bt  # noqa: E402
from app.modules.backtest.service import edge_stats as es  # noqa: E402
from app.core.config.settings import settings  # noqa: E402
from app.modules.opportunities.service import menu_builder as mb  # noqa: E402

DATA = bm.ROOT.parent / "logs" / "realdata"
CACHE = Path.home() / "month_cands.pkl"
SPLIT = "2026-10-28"

BASE = {"TARGET_R": 99.0, "TRAIL_ATR": 1.0, "BE_R": 1.5, "TRAIL_FROM_R": 2.0, "TRAIL_R": 2.0, "PER_DAY": 4, "PER_SETUP": 2,
        "FILTERS": "",
        "STOP_MIN": mb.STOP_ATR_MIN, "STOP_MAX": mb.STOP_ATR_MAX}
VARIANTS_ALL = {
    "V0 baseline (4R, trail 1.0ATR)": {},
    "V1 target 6R": {"TARGET_R": 6.0},
    "V2 target 8R, trail 1.5ATR": {"TARGET_R": 8.0, "TRAIL_ATR": 1.5},
    "V3 no target, trail 1.5ATR from 2R, BE 1.5R": {"TARGET_R": 99.0, "TRAIL_ATR": 1.5, "TRAIL_FROM_R": 2.0, "BE_R": 1.5},
    "V4 no target, trail 2ATR from 2R, BE 1.5R": {"TARGET_R": 99.0, "TRAIL_ATR": 2.0, "TRAIL_FROM_R": 2.0, "BE_R": 1.5},
    "V5 max 2/day, 1/setup": {"PER_DAY": 2, "PER_SETUP": 1},
    "V6 = V3 + max 2/day": {"TARGET_R": 99.0, "TRAIL_ATR": 1.5, "TRAIL_FROM_R": 2.0, "BE_R": 1.5, "PER_DAY": 2, "PER_SETUP": 1},
    "V7 = V4 + max 2/day": {"TARGET_R": 99.0, "TRAIL_ATR": 2.0, "TRAIL_FROM_R": 2.0, "BE_R": 1.5, "PER_DAY": 2, "PER_SETUP": 1},
    "V8 = V7 + wider stop (0.75-1.5 ATR)": {"TARGET_R": 99.0, "TRAIL_ATR": 2.0, "TRAIL_FROM_R": 2.0, "BE_R": 1.5,
                                            "PER_DAY": 2, "PER_SETUP": 1, "STOP_MIN": 0.75, "STOP_MAX": 1.5},
    "V9 = V7 + max 1/day": {"TARGET_R": 99.0, "TRAIL_ATR": 2.0, "TRAIL_FROM_R": 2.0, "BE_R": 1.5, "PER_DAY": 1, "PER_SETUP": 1},
}

VARIANTS = {
    "LIVE now (no-target R-trail)": {},
    "+ PE_GAP_UP": {"FILTERS": "PE_GAP_UP"},
    "+ PE_VIX_UP_GREEN": {"FILTERS": "PE_VIX_UP_GREEN"},
    "+ NIFTY_NOISE_STRICT": {"FILTERS": "NIFTY_NOISE_STRICT"},
    "+ NIFTY_GAP_GO_CAP": {"FILTERS": "NIFTY_GAP_GO_CAP"},
    "+ LATE_WINDOW_LAST": {"FILTERS": "LATE_WINDOW_LAST"},
    "+ all PE/NIFTY filters": {"FILTERS": "PE_GAP_UP,PE_VIX_UP_GREEN,NIFTY_NOISE_STRICT,NIFTY_GAP_GO_CAP"},
}


def load(late: bool = False):
    cache = CACHE.with_name(CACHE.stem + ("_late" if late else "") + ".pkl")
    settings.INSTITUTIONAL_FILTERS = "LATE_WINDOW_LAST" if late else ""
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    import json
    expiries = json.loads((DATA / "expiries.json").read_text())
    out = {}
    for code in bm.CODES:
        days = {d: v for d, v in bm.by_day(bm.load_csv(DATA / "index" / f"{code}.csv")).items() if len(v) >= 300}
        daily = bm.load_csv(DATA / "daily" / f"{code}.csv")
        seed = [b for b in daily if b["t"][:10] < min(days)]
        cands = bt.scan(code, days, {}, 0, True, seed_daily=seed)
        out[code] = {"days": days, "cands": cands, "exps": sorted(expiries.get(code, []))}
        print(f"scanned {code}: {len(cands)} candidate minutes", flush=True)
    cache.write_bytes(pickle.dumps(out))
    return out


def run(data, p):
    bd.DATA_DIR = DATA
    bd.MOMO_TARGET_R = p["TARGET_R"]
    bd.MOMO_TRAIL_ATR, bd.MOMO_BE_R, bd.MOMO_TRAIL_FROM_R = p["TRAIL_ATR"], p["BE_R"], p["TRAIL_FROM_R"]
    bd.MOMO_TRAIL_R = p.get("TRAIL_R")
    bd.MAX_PER_DAY, bd.MAX_PER_SETUP = p["PER_DAY"], p["PER_SETUP"]
    mb.STOP_ATR_MIN, mb.STOP_ATR_MAX = p["STOP_MIN"], p["STOP_MAX"]
    settings.INSTITUTIONAL_FILTERS = p["FILTERS"]
    bd.EXTRA_A = _extra
    trades = []
    for code, x in data.items():
        by_d = defaultdict(list)
        for cd in x["cands"]:
            by_d[cd["d"]].append(cd)
        for d in sorted(x["days"]):
            cur = next((e for e in x["exps"] if e >= d), None)
            if not cur:
                continue
            nxt = next((e for e in x["exps"] if e > cur), None)
            bd.DAY, bd.EXPIRY = d, {**bd.EXPIRY, code: cur}
            bd.NEXT_EXPIRY = {**bd.NEXT_EXPIRY, code: nxt} if nxt else {k: v for k, v in bd.NEXT_EXPIRY.items() if k != code}
            tr, _ = bd.replay(code, by_d.get(d, []), x["days"][d])
            trades += [{"day": d, "code": code, **t} for t in tr]
    return trades


_VIX: dict[str, float] = {}


def _extra(code, day, minute, cd):
    """Replay inputs the month download has: India VIX change at the open (daily candles)."""
    return {"vix": {"changePct": _VIX.get(day)}} if day in _VIX else {}


def main():
    vix = bm.load_csv(DATA / "daily" / "INDIAVIX.csv")
    for prev, cur in zip(vix, vix[1:]):
        _VIX[cur["t"][:10]] = round((cur["o"] - prev["c"]) / prev["c"] * 100, 2)
    data = load()
    data_late = load(late=True)
    hdr = (f"{'variant':<44}{'trades':>7}{'real':>5}{'win%':>6}{'net(real)':>11}{'fees':>8}{'avg':>7}{'avgWin':>8}"
           f"{'PF':>6}{'maxDD':>8}{'H1 net':>9}{'H2 net':>9}{'model':>8}")
    print(hdr + "\n" + "-" * len(hdr))
    for name, over in VARIANTS.items():
        p = {**BASE, **over}
        tr = run(data_late if "LATE_WINDOW_LAST" in p["FILTERS"] else data, p)
        real = [t for t in tr if t.get("real")]
        pn = [t["net"] for t in real]
        s = es.summarize(pn) if pn else {"n": 0}
        fees = sum(t.get("fees", 0) for t in real)
        h1 = sum(t["net"] for t in real if t["day"] < SPLIT)
        h2 = sum(t["net"] for t in real if t["day"] >= SPLIT)
        model = sum(t["net"] for t in tr if not t.get("real"))
        pf = f"{s['profitFactor']:.2f}" if s.get("profitFactor") else "-"
        print(f"{name:<44}{len(tr):>7}{len(real):>5}{s.get('winRate', 0):>6.1f}{s.get('net', 0):>+11,.0f}{fees:>8,.0f}"
              f"{s.get('expectancy', 0):>+7,.0f}{s.get('avgWin', 0):>+8,.0f}{pf:>6}{s.get('maxDrawdown', 0):>8,.0f}"
              f"{h1:>+9,.0f}{h2:>+9,.0f}{model:>+8,.0f}", flush=True)


if __name__ == "__main__":
    main()
