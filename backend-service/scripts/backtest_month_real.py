#!/usr/bin/env python3
"""
Last-month replay on REAL Upstox data (download first: scripts/fetch_month_real.py, run inside the backend container).

  * every trading day in logs/realdata/index/<CODE>.csv, NIFTY / BANKNIFTY / SENSEX
  * the live engine's rules on the real index 1-minute path (analyze -> detect -> confirm_timeframes incl. the setup
    policy -> guardrails -> strike_mode -> exits), exactly like scripts/backtest_day.py
  * each trade re-priced from the REAL 1-minute candles of the contract it would have bought (entry at the entry
    minute's open, exit at the exit minute's close, half-spread paid both ways, full charges); trades without real
    candles stay model-priced and are reported separately
  * the expiry-day iron fly on real leg prices (VRP gate from the real straddle vs Yang-Zhang realised vol, India VIX
    percentile from real VIX history when downloaded)

  PYTHONPATH=. python scripts/backtest_month_real.py [--data ../logs/realdata]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest_day as bd  # noqa: E402
import backtest_setups as bt  # noqa: E402
from app.modules.backtest.service import edge_stats as es  # noqa: E402
from app.modules.opportunities.provider.underlying_config import get_config  # noqa: E402
from app.modules.opportunities.service import event_calendar, iron_fly as fly  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
ROOT = Path(__file__).resolve().parents[1]
CODES = ("NIFTY", "BANKNIFTY", "SENSEX")


def load_csv(f: Path) -> list[dict]:
    out = []
    with open(f, newline="") as fh:
        for r in csv.DictReader(fh):
            out.append({"t": r["ts"], "o": float(r["open"]), "h": float(r["high"]), "l": float(r["low"]),
                        "c": float(r["close"]), "v": float(r.get("volume") or 0) or 1.0, "oi": float(r.get("oi") or 0)})
    out.sort(key=lambda b: b["t"])
    return out


def by_day(bars: list[dict]) -> dict[str, list[dict]]:
    d: dict[str, list[dict]] = defaultdict(list)
    for b in bars:
        d[b["t"][:10]].append(b)
    return dict(d)


def straddle_iv(straddle: float, spot: float, years: float) -> float | None:
    """ATM straddle ~ 0.8 x S x sigma x sqrt(T)  ->  sigma in % (Brenner-Subrahmanyam approximation)."""
    if straddle <= 0 or spot <= 0 or years <= 0:
        return None
    return straddle / (0.8 * spot * math.sqrt(years)) * 100


def iron_fly_day(code: str, day: str, bars: list[dict], daily_before: list[dict], vix_hist: list[float]):
    cfg = get_config(code)
    pdc = daily_before[-1]["c"]
    gap = round((bars[0]["o"] - pdc) / pdc * 100, 2)
    tags = event_calendar.event_tags(date.fromisoformat(day))
    vix_today = next((v for t, v in vix_hist if t == day), None)
    vix_pct = fly.percentile(vix_today, [v for t, v in vix_hist if t < day][-250:]) if vix_today else None
    for k, b in enumerate(bars):
        now = datetime.fromisoformat(b["t"])
        m = now.hour * 60 + now.minute
        if now.time() < fly.ENTRY_FROM:
            continue
        spot = b["c"]
        step = cfg.strikeStep
        atm = round(spot / step) * step
        strikes = [atm + i * step for i in range(-8, 9)]  # wings sit 2-6 strikes out on NIFTY / SENSEX
        rows, have = [], 0
        for s in strikes:
            row = {"strike": s}
            for sd in ("CE", "PE"):
                rb = bd.real_bars(code, s, sd == "CE")
                c = (rb or {}).get(m)
                if c:
                    h = c["c"] * bd.REAL_HALF_SPREAD_PCT / 100
                    row[sd] = {"bid": max(0.05, c["c"] - h), "ask": c["c"] + h}
                    have += 1
                else:
                    row[sd] = {"bid": 0, "ask": 0}
            rows.append(row)
        if have < 10:
            return {"day": day, "code": code, "result": "NO_DATA", "net": 0.0, "why": "no real option candles"}
        a_row = next(r for r in rows if r["strike"] == atm)
        yrs = max(1 / (252 * 375), (15 * 60 + 30 - m) / (252 * 375))
        iv = straddle_iv(a_row["CE"]["bid"] + a_row["PE"]["bid"], spot, yrs)
        wd = datetime.fromisoformat(day).weekday()
        past_rng = [b["h"] - b["l"] for b in daily_before if datetime.fromisoformat(b["t"][:10]).weekday() == wd]
        straddle = a_row["CE"]["bid"] + a_row["PE"]["bid"]
        a = {"dte": 0, "levels": {"gapPct": gap}, "vix": {}, "vrpRatio": fly.vrp_ratio(iv, daily_before),
             "impliedMoveRatio": fly.implied_move_ratio(straddle, past_rng),
             "vixPctile": vix_pct if vix_pct is not None else 50.0, "noise": {}, "dayType": {}}
        ok, why = fly.eligible(a, now, tags)
        if not ok:
            if now.time() > fly.ENTRY_TO or any("gap" in w or "event" in w or "VRP" in w or "VIX" in w for w in why):
                return {"day": day, "code": code, "result": "SKIP", "net": 0.0, "why": "; ".join(why),
                        "vrp": a["vrpRatio"], "calm": a["impliedMoveRatio"]}
            continue
        f, why_b = fly.build({"expiry": day, "strikes": rows}, spot, step, cfg.lotSize, code, cfg.exchange, gap)
        if not f:
            return {"day": day, "code": code, "result": "SKIP", "net": 0.0, "why": why_b}
        val, res, last5 = f.credit, "EOD", None
        for b2 in bars[k + 1:]:
            t2 = datetime.fromisoformat(b2["t"])
            m2 = t2.hour * 60 + t2.minute
            if m2 % 5 == 4:
                last5 = b2["c"]
            px = {}
            for act, sd, s2, _p, _key in f.legs:
                c = (bd.real_bars(code, s2, sd == "CE") or {}).get(m2)
                if c:
                    h = c["c"] * bd.REAL_HALF_SPREAD_PCT / 100
                    px[(sd, s2)] = c["c"] + h if act == "SELL" else max(0.05, c["c"] - h)
            if len(px) < 4:
                continue
            val = fly.fly_value(px, f)
            r = fly.check_exit(f, val, t2, last5)
            if r:
                res = r
                break
        return {"day": day, "code": code, "result": res, "net": fly.pnl_rs(f, val), "vrp": a["vrpRatio"],
                "calm": a["impliedMoveRatio"],
                "why": f"{now:%H:%M} {f.putWing:.0f}/{f.atm:.0f}/{f.callWing:.0f} credit {f.credit:.1f} -> {val:.1f}"}
    return {"day": day, "code": code, "result": "SKIP", "net": 0.0, "why": "never eligible"}


def table(title, groups):
    print(f"\n{title}")
    print(f"  {'':<24}{'n':>4}{'win%':>7}{'net Rs':>11}{'avg':>8}{'PF':>7}")
    for k, p in sorted(groups.items(), key=lambda kv: -sum(kv[1])):
        s = es.summarize(p)
        pf = f"{s['profitFactor']:.2f}" if s.get("profitFactor") else "-"
        print(f"  {k:<24}{s['n']:>4}{s['winRate']:>7.1f}{s['net']:>+11,.0f}{s['expectancy']:>+8,.0f}{pf:>7}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT.parent / "logs" / "realdata")
    ap.add_argument("--codes", nargs="+", default=list(CODES))
    a = ap.parse_args()
    data = a.data
    bd.DATA_DIR = data
    ej = data / "expiries.json"
    expiries = json.loads(ej.read_text()) if ej.exists() else {  # download still running: series from folder names
        c: sorted(p.name for p in (data / "expired" / c).iterdir()) for c in CODES if (data / "expired" / c).exists()}
    vix_f = data / "daily" / "INDIAVIX.csv"
    vix_hist = [(b["t"][:10], b["c"]) for b in load_csv(vix_f)] if vix_f.exists() else []
    trades, flies = [], []
    for code in a.codes:
        f = data / "index" / f"{code}.csv"
        if not f.exists():
            print(f"{code}: no index data")
            continue
        days = by_day(load_csv(f))
        days = {d: v for d, v in days.items() if len(v) >= 300}
        daily_all = load_csv(data / "daily" / f"{code}.csv")
        first = min(days)
        seed = [b for b in daily_all if b["t"][:10] < first]
        exps = sorted(expiries.get(code, []))
        cands = bt.scan(code, days, {}, 0, True, seed_daily=seed)
        by_d: dict[str, list] = defaultdict(list)
        for cd in cands:
            by_d[cd["d"]].append(cd)
        for d in sorted(days):
            cur = next((e for e in exps if e >= d), None)
            if not cur:
                continue
            nxt = next((e for e in exps if e > cur), None)
            bd.DAY, bd.EXPIRY = d, {**bd.EXPIRY, code: cur}
            bd.NEXT_EXPIRY = {**bd.NEXT_EXPIRY, code: nxt} if nxt else {k: v for k, v in bd.NEXT_EXPIRY.items() if k != code}
            tr, _seen = bd.replay(code, by_d.get(d, []), days[d])
            for t in tr:
                trades.append({"day": d, "code": code, **t})
            if cur == d:
                daily_before = [b for b in daily_all if b["t"][:10] < d]
                flies.append(iron_fly_day(code, d, days[d], daily_before, vix_hist))
        print(f"{code}: {len(days)} days {min(days)}..{max(days)}, {sum(1 for t in trades if t['code'] == code)} trades",
              flush=True)

    real = [t for t in trades if t.get("real")]
    model = [t for t in trades if not t.get("real")]
    print(f"\n=== MONTH REPLAY on real Upstox data: {len(trades)} momentum-engine trades "
          f"({len(real)} priced from REAL option candles, {len(model)} model-priced: no candle file) ===")
    for t in trades:
        tag = "REAL " if t.get("real") else "model"
        print(f"  {t['day']} {t['code']:<9} {t['time']} {t['setup']:<18} {t['side']} {t['strike']:>6} {tag} "
              f"Rs {t['p0']:8.2f} -> {t['px']:8.2f} ({t['pct']:+5.1f}%) {t['out']:<11} {t['hold']:>3}m  net Rs {t['net']:+9,.0f}")
    if real:
        table("REAL-priced trades by setup", {f"{t['setup']} {t['side']}": [x['net'] for x in real
                                                if x['setup'] == t['setup'] and x['side'] == t['side']] for t in real})
        table("REAL-priced trades by underlying", {c: [t["net"] for t in real if t["code"] == c] for c in CODES
                                                   if any(t["code"] == c for t in real)})
        s = es.summarize([t["net"] for t in real])
        lo, hi = s["ci95"]
        print(f"\n  REAL total: n={s['n']} win {s['winRate']}% net Rs {s['net']:+,.0f}  expectancy Rs {s['expectancy']:+,.0f}"
              f"/trade  95% CI [{lo:+,.0f}, {hi:+,.0f}]  PF {s.get('profitFactor')}  max DD Rs {s['maxDrawdown']:,.0f}")
        print(f"  verdict: {es.promotion_verdict([t['net'] for t in real], 200)[1]}")
    if model:
        print(f"\n  model-priced (no real candles) total: n={len(model)} net Rs {sum(t['net'] for t in model):+,.0f}")
    print("\n=== EXPIRY-DAY IRON FLY on real leg prices ===")
    for x in flies:
        print(f"  {x['day']} {x['code']:<9} {x['result']:<11} net Rs {x['net']:+8,.0f}  vrp {x.get('vrp')} "
              f"calm {x.get('calm')}  {x['why']}")
    traded = [x["net"] for x in flies if x["result"] not in ("SKIP", "NO_DATA")]
    print(f"  iron fly: {len(traded)} traded, net Rs {sum(traded):+,.0f}" + ("" if vix_hist else
          "  (India VIX history missing: VIX-percentile gate assumed to pass)"))
    out = ROOT / "backtest_out" / f"month_real_{date.today().isoformat()}.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["day", "underlying", "time_ist", "strategy", "side", "strike", "priced", "entry", "exit", "pct",
                    "outcome", "hold_min", "net"])
        for t in trades:
            w.writerow([t["day"], t["code"], t["time"], t["setup"], t["side"], t["strike"],
                        "REAL" if t.get("real") else "MODEL", round(t["p0"], 2), round(t["px"], 2), round(t["pct"], 2),
                        t["out"], t["hold"], round(t["net"], 2)])
        for x in flies:
            if x["result"] not in ("SKIP", "NO_DATA"):
                w.writerow([x["day"], x["code"], "", "IRON_FLY", "FLY", "", "REAL", "", "", "", x["result"], "",
                            round(x["net"], 2)])
    print(f"\nCSV: {out}")


if __name__ == "__main__":
    main()
