#!/usr/bin/env python3
"""
Min-loss / max-profit search on the 6-month data (logs/realdata6m). Uses the cached engine scans; each variant changes
only WHICH signals are taken and how the trade is managed. A variant counts only if it is better in BOTH halves.
Prices: real option candles where downloaded, otherwise the Black-Scholes estimate (reported as such).

  PYTHONPATH=. python scripts/optimize_range.py [--only V1,V2]
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest_day as bd  # noqa: E402
import backtest_range_real as r  # noqa: E402
from app.modules.backtest.service import edge_stats as es  # noqa: E402
from app.modules.opportunities.service import menu_builder as mb  # noqa: E402

SPLIT = "2026-08-17"
MOMO = ("NOISE_BREAKOUT", "LATE_DAY_MOMENTUM", "RANGE_BREAKOUT", "VWAP_PULLBACK", "GAP_GO")


def prefilter(data, keep):
    """Copy of the scans with only the raw signals `keep(cd, s)` accepts."""
    out = {}
    for code, x in data.items():
        cands = []
        for cd in x["cands"]:
            raw = [s for s in cd["raw"] if keep(code, cd, s)]
            if raw:
                cands.append({**cd, "raw": raw})
        out[code] = {**x, "cands": cands}
    return out


def with_trend(code, cd, s):
    """Higher-timeframe alignment: CE only when the multi-day trend is UP, PE only when DOWN."""
    t = cd.get("dtrend")
    return t is None or (s["side"] == "CE") == (t == "UP")


_TREND: dict[tuple[str, str, int], str] = {}


def trend_n(n):
    """Multi-day trend over n sessions from the daily closes BEFORE the trading day (no look-ahead)."""
    def f(code, cd, s):
        t = _TREND.get((code, cd["d"], n))
        return t is None or (s["side"] == "CE") == (t == "UP")
    return f


def build_trends(data, ns=(5, 10, 20)):
    for code, x in data.items():
        closes = [(b["t"][:10], b["c"]) for b in x["daily"]]
        for d in x["days"]:
            prior = [c for t, c in closes if t < d]
            for n in ns:
                if len(prior) > n:
                    _TREND[(code, d, n)] = "UP" if prior[-1] > prior[-1 - n] else "DOWN"


def expansion_only(code, cd, s):
    """Momentum only once the day has proven it trends: day type / sticky bias TREND or EXPANSION on that side."""
    dt, b = cd.get("dayType") or {}, cd.get("dayBias") or {}
    return any(x.get("type") in ("TREND", "EXPANSION") and x.get("side") == s["side"] for x in (dt, b))


def no_vwap_pullback(code, cd, s):
    return s["name"] != "VWAP_PULLBACK"


def time_window(lo, hi):
    return lambda code, cd, s: lo <= cd["m"] <= hi


def all_of(*fs):
    return lambda code, cd, s: all(f(code, cd, s) for f in fs)


VARIANTS = {
    "V0 LIVE now": ({}, None),
    "V1 trade WITH multi-day trend": ({}, with_trend),
    "V2 no VWAP_PULLBACK": ({}, no_vwap_pullback),
    "V3 entries 10:00-14:30 only": ({}, time_window(600, 870)),
    "V4 = V1 + V2": ({}, all_of(with_trend, no_vwap_pullback)),
    "V5 = V1 + V2 + V3": ({}, all_of(with_trend, no_vwap_pullback, time_window(600, 870))),
    "V6 = V4 + wider stop 0.75-1.5ATR": ({"STOP": (0.75, 1.5)}, all_of(with_trend, no_vwap_pullback)),
    "V7 = V4 + tighter stop 0.4-1.0ATR": ({"STOP": (0.4, 1.0)}, all_of(with_trend, no_vwap_pullback)),
    "V8 = V4 + max 2/day 1/setup": ({"PER_DAY": 2, "PER_SETUP": 1}, all_of(with_trend, no_vwap_pullback)),
    "V9 = V4 + BE at 1R": ({"BE_R": 1.0}, all_of(with_trend, no_vwap_pullback)),
    "V10 = V8 + 10:00-14:30": ({"PER_DAY": 2, "PER_SETUP": 1}, all_of(with_trend, no_vwap_pullback, time_window(600, 870))),
    "V11 = V4 with 10-day trend": ({}, all_of(trend_n(10), no_vwap_pullback)),
    "V12 = V4 with 20-day trend": ({}, all_of(trend_n(20), no_vwap_pullback)),
    "V13 = V4 + 5d AND 20d trend": ({}, all_of(trend_n(5), trend_n(20), no_vwap_pullback)),
    "V14 = V4 + trend-day only": ({}, all_of(with_trend, no_vwap_pullback, expansion_only)),
    "V15 = V10 + 5d AND 20d trend": ({"PER_DAY": 2, "PER_SETUP": 1},
                                     all_of(trend_n(5), trend_n(20), no_vwap_pullback, time_window(600, 870))),
}


def run(ctx, data, over, keep):
    stop0 = (mb.STOP_ATR_MIN, mb.STOP_ATR_MAX)
    be0 = bd.MOMO_BE_R
    try:
        if "STOP" in over:
            mb.STOP_ATR_MIN, mb.STOP_ATR_MAX = over["STOP"]
        bd.MOMO_BE_R = over.get("BE_R", be0)
        bd.MAX_PER_DAY, bd.MAX_PER_SETUP = over.get("PER_DAY"), over.get("PER_SETUP")
        d = prefilter(data, keep) if keep else data
        return r.run_momentum(ctx, d, r.LIVE)
    finally:
        mb.STOP_ATR_MIN, mb.STOP_ATR_MAX = stop0
        bd.MOMO_BE_R = be0
        bd.MAX_PER_DAY = bd.MAX_PER_SETUP = None


def report(name, tr):
    p = [t["net"] for t in tr]
    s = es.summarize(p) if p else {"n": 0}
    losses = [x for x in p if x <= 0]
    h1 = sum(t["net"] for t in tr if t["day"] < SPLIT)
    h2 = sum(t["net"] for t in tr if t["day"] >= SPLIT)
    real = sum(1 for t in tr if t.get("real"))
    pf = f"{s['profitFactor']:.2f}" if s.get("profitFactor") else "-"
    print(f"{name:<36}{s['n']:>5}{real:>5}{s.get('winRate', 0):>6.1f}{s.get('net', 0):>+10,.0f}{sum(losses):>+10,.0f}"
          f"{(sum(losses) / len(losses) if losses else 0):>+8,.0f}{s.get('avgWin', 0):>+8,.0f}{pf:>6}"
          f"{s.get('maxDrawdown', 0):>9,.0f}{h1:>+10,.0f}{h2:>+10,.0f}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    data_dir = r.ROOT.parent / "logs" / "realdata6m"
    bd.DATA_DIR = data_dir
    ctx = r.Ctx(data_dir)
    data = r.scan_all(ctx, False)
    build_trends(data)
    print(f"{'variant':<36}{'n':>5}{'real':>5}{'win%':>6}{'net':>10}{'losses':>10}{'avgLoss':>8}{'avgWin':>8}{'PF':>6}"
          f"{'maxDD':>9}{'H1':>10}{'H2':>10}")
    names = [n for n in VARIANTS if not a.only or n.split()[0] in a.only.split(",")]
    for n in names:
        over, keep = VARIANTS[n]
        report(n, run(ctx, copy.copy(data), over, keep))


if __name__ == "__main__":
    main()
