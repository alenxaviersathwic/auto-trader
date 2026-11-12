#!/usr/bin/env python3
"""
Intraday setup backtester: replays 1-minute candles through the SAME code the live engine runs
(market_analysis.analyze -> setups.detect -> setups.confirm_timeframes), one minute at a time,
then simulates each accepted setup with the menu's own premium target / stop rules.

  python scripts/backtest_setups.py fetch --codes NIFTY BANKNIFTY --days 120     # needs DB + Upstox token (your Mac)
  python scripts/backtest_setups.py run   --codes NIFTY BANKNIFTY --sweep        # pure CPU, reads the CSV cache
  python scripts/backtest_setups.py selftest                                       # synthetic data, pipeline smoke test

What is and is not measured (read this before trusting a number):
  * No historical option chains exist, so premium P&L is a PROXY: premium0 = premium-pct x spot and
    pnl% = delta x underlying move / premium0 - theta drag - round-trip costs. Gamma, IV change and
    real spreads are ignored. Treat results as a RANKING of setups, not a P&L forecast.
  * Spot indices have no volume. Without futures candles, VWAP is a TWAP proxy and volume-spike / OI
    buildup confirmations are absent (those setups run weaker than live). Results are tagged FUT / PROXY.
  * OI_WALL_REJECT and PCR_SHIFT need option-chain history and CANNOT be replayed; the report lists them
    as untestable. Forward-test them with the saved-opportunity outcome checker instead.
  * Fill = OPEN of the minute after the signal minute; slippage is a flat % of premium. Stop is checked before target inside
    a bar that touches both. One position at a time per underlying.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import math
import random
import statistics
import sys
import tempfile
from bisect import bisect_left
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.modules.opportunities.provider.underlying_config import get_config  # noqa: E402
from app.modules.opportunities.service import day_type, setups as setup_detector  # noqa: E402
from app.modules.opportunities.service.costs import round_trip_cost_pct  # noqa: E402
from app.modules.opportunities.service.market_analysis import _bar_min, _mins, analyze  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
FIELDS = ["t", "o", "h", "l", "c", "v", "oi"]
ALL_SETUPS = ["ORB", "VWAP_PULLBACK", "PDH_PDL_RETEST", "CPR_BREAKOUT", "OI_WALL_REJECT", "MOMENTUM_FLAG",
              "EMA_CROSS_RETEST", "SUPERTREND_FLIP", "SUPERTREND_RETEST", "INSIDE_BAR", "RANGE_BREAKOUT",
              "GAP_GO", "PCR_SHIFT", "SHORT_COVERING_SPIKE", "FAILED_BREAK_RECLAIM", "VWAP_BAND_REVERT",
              "NOISE_BREAKOUT", "LATE_DAY_MOMENTUM"]
UNTESTABLE = {"OI_WALL_REJECT": "needs historical option-chain OI", "PCR_SHIFT": "needs historical option-chain OI"}
MIN_BARS_PER_DAY = 300  # skip holidays / half days / partial downloads


# ───────────────────────── data ─────────────────────────
def write_csv(path: Path, bars: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for b in bars:
            w.writerow({k: b.get(k, 0) for k in FIELDS})


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open() as f:
        return [{"t": r["t"], **{k: float(r[k]) for k in FIELDS[1:]}} for r in csv.DictReader(f)]


def by_day(bars: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in sorted(bars, key=lambda x: x["t"]):
        out[b["t"][:10]].append(b)
    return dict(out)


def day_bar(bars: list[dict[str, Any]]) -> dict[str, Any]:
    return {"t": bars[0]["t"], "o": bars[0]["o"], "h": max(b["h"] for b in bars), "l": min(b["l"] for b in bars),
            "c": bars[-1]["c"], "v": sum(b["v"] for b in bars), "oi": bars[-1]["oi"]}


# ───────────────────────── scan: run the real engine code each minute ─────────────────────────
def scan(code: str, spot_days: dict[str, list[dict[str, Any]]], fut_days: dict[str, list[dict[str, Any]]],
         warmup: int, proxy: bool, seed_daily: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    cfg = get_config(code)
    assert cfg is not None
    open_m = _mins(cfg.open)
    daily: list[dict[str, Any]] = list(seed_daily or [])
    cands: list[dict[str, Any]] = []
    seen_days = 0
    lookback = max(5, min(warmup, 20))
    for d in sorted(spot_days):
        bars = spot_days[d]
        if len(bars) < MIN_BARS_PER_DAY:
            continue
        if seen_days >= warmup:
            fut, src = fut_days.get(d) or [], "FUT"
            if len(fut) < MIN_BARS_PER_DAY:
                fut, src = ([{**b, "v": 1.0, "oi": 0.0} for b in bars], "PROXY") if proxy else ([], "NONE")
            mins = [_bar_min(b["t"]) for b in bars]
            fmins = [_bar_min(b["t"]) for b in fut]
            y, mo, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
            close_m = _mins(cfg.close_today(datetime(y, mo, dd, 12, 0, tzinfo=IST)))  # 15:30 before 3 Aug 2026
            bias_state: dict[str, Any] = {}  # sticky day-type call for THIS day only (day_type.apply_bias())
            for k in range(1, len(bars)):
                m = mins[k]
                if m < open_m + 6:
                    continue
                if m > close_m - 20:
                    break
                fi = bisect_left(fmins, m)
                market = {"spot": bars[k - 1]["c"], "spotBars1m": bars[:k], "futBars1m": fut[:fi],
                          "daily": daily, "chains": [], "vix": None}
                a = analyze(cfg, market, datetime(y, mo, dd, m // 60, m % 60, tzinfo=IST))
                if a["session"]["blocked"]:
                    continue
                bias_state = day_type.apply_bias(a.get("dayType") or {}, bias_state, m)
                raw = setup_detector.detect(a, cfg)
                if raw:
                    cands.append({"d": d, "k": k, "m": m, "raw": raw, "trend15": a.get("trend15"),
                                  "atr5": a.get("atr5") or 0.0, "bars1": a["bars1"][-30:],
                                  "sig5": a["bars5"][-1]["start"], "regime": a.get("regime"),
                                  "window": a["session"]["window"], "src": src, "dayType": a.get("dayType"), "noise": a.get("noise"),
                                  "dayBias": bias_state.get("bias"), "levels": dict(a.get("levels") or {}),
                                  "dtrend": None if len(daily) < lookback else ("UP" if daily[-1]["c"] > daily[-lookback]["c"] else "DOWN")})
        daily.append(day_bar(bars))
        seen_days += 1
    return cands


def _scan_job(args: tuple[str, str, bool, int]) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
    code, data_dir, proxy, warmup = args
    spot = by_day(read_csv(Path(data_dir) / f"{code}_spot_1m.csv"))
    fut = by_day(read_csv(Path(data_dir) / f"{code}_fut_1m.csv"))
    cov = {"days": sum(1 for v in spot.values() if len(v) >= MIN_BARS_PER_DAY), "futDays": sum(1 for v in fut.values() if len(v) >= MIN_BARS_PER_DAY)}
    return code, scan(code, spot, fut, warmup, proxy), cov


# ───────────────────────── evaluate: gate + simulate ─────────────────────────
@dataclass(frozen=True)
class SimCfg:
    gate: str = "full"          # off = 15m trend only | legacy = + last 1m bar colour | full = one_minute_check()
    stop_mode: str = "capped"   # capped = today's engine | chart = chart stop converted to premium | skip = skip if chart stop > cap
    delta: float = 0.5
    prem_pct: float = 0.5       # ATM premium as % of spot (assumption!)
    min_margin: float = 5.0
    max_margin: float = 10.0
    min_stop: float = 2.5
    max_stop: float = 3.5
    theta_per_hr: float = 1.0   # premium % lost per hour from time decay (assumption)
    slip_pct: float = 0.6       # round-trip slippage/spread, % of premium (assumption)
    max_hold: int = 45
    max_trades_day: int = 4
    daily_filter: bool = False  # time-series-momentum filter: trade only WITH the multi-week daily trend

    def label(self) -> str:
        return f"gate={self.gate} stop={self.stop_mode}" + (" +dailyTSMOM" if self.daily_filter else "")


def gate_ok(cd: dict[str, Any], s: dict[str, Any], c: SimCfg) -> bool:
    ce = s["side"] == "CE"
    if cd["trend15"] != ("UP" if ce else "DOWN"):
        return False
    if c.daily_filter and cd.get("dtrend") != ("UP" if ce else "DOWN"):
        return False
    if c.gate == "off":
        return True
    b1 = cd["bars1"]
    if c.gate == "legacy":
        if len(b1) < 2:
            return False
        l1, p1 = b1[-1], b1[-2]
        return (l1["c"] > l1["o"] and l1["c"] >= p1["c"]) if ce else (l1["c"] < l1["o"] and l1["c"] <= p1["c"])
    ok, _ = setup_detector.confirm_timeframes({"trend15": cd["trend15"], "bars1": b1, "atr5": cd["atr5"],
                                               "dayType": cd.get("dayType"), "dayBias": cd.get("dayBias"),
                                               "levels": cd.get("levels")}, [s])
    return bool(ok)


def sim_trade(bars: list[dict[str, Any]], k: int, s: dict[str, Any], c: SimCfg, code: str) -> tuple[dict[str, Any] | None, str]:
    cfg = get_config(code)
    assert cfg is not None
    ce = s["side"] == "CE"
    sg = 1 if ce else -1
    fill = bars[k]["o"]
    up, down = (s["target"] - fill) * sg, (fill - s["stop"]) * sg
    if up <= 0 or down <= 0:
        return None, "price ran past setup plan"
    p0 = fill * c.prem_pct / 100
    tgt = min(c.max_margin, c.delta * up * 0.9 / p0 * 100)
    if tgt < c.min_margin:
        return None, "no room for min target"
    chart = c.delta * down / p0 * 100
    if c.stop_mode == "capped":
        stop = max(min(c.min_stop, c.max_stop), min(c.max_stop, chart))
    elif c.stop_mode == "chart":
        stop = max(c.min_stop, chart)
    else:
        if chart > c.max_stop:
            return None, "chart stop wider than cap"
        stop = max(c.min_stop, chart)
    if tgt / stop < 1.2:
        return None, "reward:risk<1.2"
    cost = round_trip_cost_pct(p0, cfg.lotSize, cfg.exchange, tgt)
    close_m = _mins(cfg.close_today())
    m0 = _bar_min(bars[k]["t"])
    mfe = mae = 0.0
    out, pnl, j = "TIME", 0.0, k
    for j in range(k, len(bars)):
        b = bars[j]
        m = _bar_min(b["t"])
        theta = c.theta_per_hr * (m + 1 - m0) / 60
        fav = c.delta * (((b["h"] if ce else b["l"]) - fill) * sg) / p0 * 100 - theta
        adv = c.delta * (((b["l"] if ce else b["h"]) - fill) * sg) / p0 * 100 - theta
        mfe, mae = max(mfe, fav), min(mae, adv)
        if adv <= -stop:
            out, pnl = "STOP", -stop
            break
        if fav >= tgt:
            out, pnl = "TARGET", tgt
            break
        pnl = c.delta * ((b["c"] - fill) * sg) / p0 * 100 - theta
        if m - m0 >= c.max_hold or m >= close_m - 10:
            out = "TIME" if m - m0 >= c.max_hold else "EOD"
            break
    return {"exitK": j, "outcome": out, "grossPct": round(pnl, 2), "costPct": cost, "netPct": round(pnl - cost - c.slip_pct, 2),
            "tgtPct": round(tgt, 1), "stopPct": round(stop, 1), "holdMin": _bar_min(bars[j]["t"]) - m0 + 1,
            "mfePct": round(mfe, 1), "maePct": round(mae, 1), "fill": round(fill, 2)}, ""


def evaluate(code: str, cands: list[dict[str, Any]], spot_days: dict[str, list[dict[str, Any]]], c: SimCfg
             ) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]], dict[str, int]]:
    trades: list[dict[str, Any]] = []
    funnel: dict[str, dict[str, int]] = defaultdict(lambda: {"raw": 0, "gated": 0, "traded": 0})
    skips: dict[str, int] = defaultdict(int)
    raw_seen: set[tuple] = set()
    taken: set[tuple] = set()
    busy: dict[str, int] = {}
    per_day: dict[str, int] = defaultdict(int)
    for cd in cands:
        d, k = cd["d"], cd["k"]
        for s in cd["raw"]:
            rk = (d, s["name"], s["side"], cd["sig5"])
            if rk not in raw_seen:
                raw_seen.add(rk)
                funnel[s["name"]]["raw"] += 1
        if k <= busy.get(d, -1) or per_day[d] >= c.max_trades_day:
            continue
        for s in cd["raw"]:
            key = (d, s["name"], s["side"], cd["sig5"])
            if key in taken or not gate_ok(cd, s, c):
                continue
            taken.add(key)
            funnel[s["name"]]["gated"] += 1
            res, why = sim_trade(spot_days[d], k, s, c, code)
            if res is None:
                skips[why] += 1
                continue
            funnel[s["name"]]["traded"] += 1
            per_day[d] += 1
            busy[d] = res["exitK"]
            trades.append({"code": code, "date": d, "time": f"{cd['m'] // 60:02d}:{cd['m'] % 60:02d}", "setup": s["name"],
                           "side": s["side"], "strength": s["strength"], "regime": cd["regime"], "window": cd["window"],
                           "src": cd["src"], **res})
            break  # one position at a time: best-strength setup that passed
    return trades, dict(funnel), dict(skips)


# ───────────────────────── statistics + report ─────────────────────────
def stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {"n": 0}
    net = [r["netPct"] for r in rows]
    wins, losses = [x for x in net if x > 0], [x for x in net if x <= 0]
    sd = statistics.pstdev(net) if n > 1 else 0.0
    return {"n": n, "target%": round(100 * sum(r["outcome"] == "TARGET" for r in rows) / n, 1),
            "win%": round(100 * len(wins) / n, 1), "avgNet%": round(sum(net) / n, 2),
            "avgWin%": round(sum(wins) / len(wins), 2) if wins else 0.0,
            "avgLoss%": round(sum(losses) / len(losses), 2) if losses else 0.0,
            "PF": round(sum(wins) / -sum(losses), 2) if losses and sum(losses) < 0 else None,
            "t": round((sum(net) / n) / (sd / math.sqrt(n)), 2) if sd > 0 else 0.0,
            "hold": round(sum(r["holdMin"] for r in rows) / n)}


def verdict(st: dict[str, Any]) -> str:
    if st["n"] < 30:
        return "INSUFFICIENT (<30)"
    if st["avgNet%"] > 0 and st["t"] >= 1.5:
        return "KEEP"
    return "WATCH" if st["avgNet%"] > 0 else "DROP"


def table(rows: list[tuple[str, dict[str, Any]]], head: str) -> str:
    cols = ["n", "target%", "win%", "avgNet%", "avgWin%", "avgLoss%", "PF", "t", "hold"]
    out = [f"| {head} | " + " | ".join(cols) + " | verdict |", "|" + "---|" * (len(cols) + 2)]
    for name, st in rows:
        if st["n"] == 0:
            out.append(f"| {name} | 0 |" + " |" * (len(cols) - 1) + " | - |")
        else:
            out.append(f"| {name} | " + " | ".join(str(st.get(c, "")) for c in cols) + f" | {verdict(st)} |")
    return "\n".join(out)


def group(trades: list[dict[str, Any]], key) -> list[tuple[str, dict[str, Any]]]:
    g: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        g[key(t)].append(t)
    return sorted(((k, stats(v)) for k, v in g.items()), key=lambda x: -x[1].get("avgNet%", -999))


def build_report(args: argparse.Namespace, cov: dict[str, dict[str, int]], sweep: list[tuple[SimCfg, list, dict, dict]],
                 main_idx: int) -> str:
    main_cfg, trades, funnel, skips = sweep[main_idx]
    L = [f"# Setup backtest report ({date.today()})", "",
         f"Underlyings: {', '.join(cov)} | warm-up days: {args.warmup} | premium proxy: {main_cfg.prem_pct}% of spot, "
         f"delta {main_cfg.delta}, theta {main_cfg.theta_per_hr}%/h, round-trip slippage {main_cfg.slip_pct}%, "
         f"target {main_cfg.min_margin}-{main_cfg.max_margin}%, stop {main_cfg.min_stop}-{main_cfg.max_stop}%", "",
         "Coverage (trading days replayed / with real futures candles): " +
         ", ".join(f"{k} {v['days'] - args.warmup}/{v['futDays']}" for k, v in cov.items()), "",
         "> Premium P&L is a delta-proxy, not real option prices. Use it to RANK setups and test rule changes, "
         "not to forecast rupees. `PROXY` rows used spot-TWAP in place of futures VWAP and had no volume/OI confirmation.", ""]
    if len(sweep) > 1:
        L += ["## Variant comparison (same signals, different rules)", ""]
        rows = [(c.label() + (" **(main)**" if i == main_idx else ""), stats(t)) for i, (c, t, _, _) in enumerate(sweep)]
        L += [table(rows, "variant"), ""]
    L += [f"## Main variant: {main_cfg.label()}", "", "### By setup", "", table(group(trades, lambda t: t["setup"]), "setup"), "",
          "### By setup and side", "", table(group(trades, lambda t: f"{t['setup']} {t['side']}"), "setup/side"), "",
          "### By underlying", "", table(group(trades, lambda t: t["code"]), "underlying"), "",
          "### By time window", "", table(group(trades, lambda t: t["window"]), "window"), "",
          "### By regime", "", table(group(trades, lambda t: t["regime"]), "regime"), "",
          "### By data source", "", table(group(trades, lambda t: t["src"]), "src"), "",
          "### By entry hour", "", table(group(trades, lambda t: t["time"][:2] + ":00"), "hour"), ""]
    L += ["### Signal funnel (unique signals)", "", "| setup | raw | passed gate | traded | note |", "|---|---|---|---|---|"]
    for name in ALL_SETUPS:
        f = funnel.get(name, {"raw": 0, "gated": 0, "traded": 0})
        L.append(f"| {name} | {f['raw']} | {f['gated']} | {f['traded']} | {UNTESTABLE.get(name, '')} |")
    if skips:
        L += ["", "### Why gated signals were not traded", ""] + [f"- {k}: {v}" for k, v in sorted(skips.items(), key=lambda x: -x[1])]
    L += ["", "### Read this honestly", "",
          "- `KEEP` needs n>=30, positive average net return AND t>=1.5. Anything else is not evidence.",
          "- Fewer than ~100 trades per setup over a single regime period will not generalise; extend the date range before changing live rules.",
          "- Compare variants on the SAME data; a rule change that wins in the sweep still needs a forward test."]
    return "\n".join(L)


def run_backtest(args: argparse.Namespace) -> str:
    data_dir = Path(args.data_dir)
    jobs = [(c.upper(), str(data_dir), not args.no_proxy, args.warmup) for c in args.codes]
    with ProcessPoolExecutor(max_workers=max(1, min(args.workers, len(jobs)))) as ex:
        scanned = list(ex.map(_scan_job, jobs)) if len(jobs) > 1 and args.workers > 1 else [_scan_job(j) for j in jobs]
    cov = {code: c for code, _, c in scanned}
    spot = {code: by_day(read_csv(data_dir / f"{code}_spot_1m.csv")) for code, _, _ in scanned}
    base = SimCfg(gate=args.gate, stop_mode=args.stop_mode, prem_pct=args.premium_pct, delta=args.delta,
                  min_margin=args.min_margin, max_margin=args.max_margin, max_stop=args.max_stop,
                  theta_per_hr=args.theta, slip_pct=args.slip_pct, max_hold=args.max_hold, max_trades_day=args.max_trades_day, daily_filter=args.daily_filter)
    variants = [base]
    if args.sweep:
        variants = [SimCfg(**{**asdict(base), "gate": g, "stop_mode": sm, "daily_filter": False}) for g in ("off", "legacy", "full") for sm in ("capped", "chart", "skip")]
        variants += [SimCfg(**{**asdict(base), "gate": "full", "stop_mode": sm, "daily_filter": True}) for sm in ("capped", "chart", "skip")]
    sweep = []
    for v in variants:
        tr: list[dict[str, Any]] = []
        fun: dict[str, dict[str, int]] = defaultdict(lambda: {"raw": 0, "gated": 0, "traded": 0})
        sk: dict[str, int] = defaultdict(int)
        for code, cands, _ in scanned:
            t, f, s = evaluate(code, cands, spot[code], v)
            tr += t
            for n, d in f.items():
                for kk, vv in d.items():
                    fun[n][kk] += vv
            for n, vv in s.items():
                sk[n] += vv
        sweep.append((v, tr, dict(fun), dict(sk)))
    main_idx = next(i for i, (v, *_) in enumerate(sweep) if (v.gate, v.stop_mode, v.daily_filter) == (base.gate, base.stop_mode, base.daily_filter))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    trades = sweep[main_idx][1]
    if trades:
        with (out / "trades.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
            w.writeheader()
            w.writerows(trades)
    report = build_report(args, cov, sweep, main_idx)
    (out / "REPORT.md").write_text(report)
    return report


# ───────────────────────── fetch (needs the app's DB + Upstox token) ─────────────────────────
async def fetch(args: argparse.Namespace) -> None:
    from app.core.db.session import async_session_factory
    from app.modules.opportunities.provider.instrument_catalog import instrument_catalog
    from app.modules.opportunities.provider.upstox_market_data import market_data

    end = date.today() if not args.to else date.fromisoformat(args.to)
    start = (date.fromisoformat(args.start) if args.start else end - timedelta(days=args.days)) - timedelta(days=32)  # + warm-up
    step = timedelta(days=args.chunk_days)
    async with async_session_factory() as s:
        for code in [c.upper() for c in args.codes]:
            cfg = get_config(code)
            if cfg is None or not cfg.instrumentKey:
                print(f"{code}: skipped (no fixed instrument key; MCX futures roll monthly and expired contracts have no history)")
                continue
            keys = {"spot": cfg.instrumentKey}
            try:
                fut = await instrument_catalog.near_future(cfg.exchange, code)
                if fut:
                    keys["fut"] = fut.key
            except Exception as e:  # noqa: BLE001
                print(f"{code}: no futures key ({e})")
            for kind, key in keys.items():
                bars: list[dict[str, Any]] = []
                cur = start
                while cur <= end:
                    nxt = min(cur + step, end)
                    got = await market_data.candles_1m_range(key, cur.isoformat(), nxt.isoformat(), s)
                    print(f"{code} {kind} {cur}..{nxt}: {len(got)} bars")
                    bars += got
                    cur = nxt + timedelta(days=1)
                    await asyncio.sleep(0.4)
                uniq = {b["t"]: b for b in bars}
                write_csv(Path(args.data_dir) / f"{code}_{kind}_1m.csv", sorted(uniq.values(), key=lambda x: x["t"]))
                print(f"{code} {kind}: wrote {len(uniq)} bars")
    print("Note: the futures file only covers the CURRENT near-month contract; earlier days fall back to the spot-TWAP proxy.")


# ───────────────────────── synthetic data (selftest only: proves the pipeline, says nothing about edge) ─────────────────────────
def synth_day(rnd: random.Random, d: date, start_px: float, trending: bool = True) -> list[dict[str, Any]]:
    """Path-consistent 1-minute bars: each minute is 4 sub-ticks, so highs/lows are real touches of the path."""
    drift = rnd.choice([-1, 0, 0, 1]) * rnd.uniform(0.2, 0.9) if trending else 0.0
    vol = rnd.uniform(1.5, 4.5)
    px, oi, out = start_px * (1 + rnd.uniform(-0.004, 0.004)), 1_000_000.0, []
    for i in range(375):
        mm = 9 * 60 + 15 + i
        burst = 3.0 if rnd.random() < 0.02 else 1.0
        ticks = [px]
        for _ in range(4):
            ticks.append(ticks[-1] + rnd.gauss(drift, vol * burst) / 2)
        oi += rnd.gauss(0, 800)
        out.append({"t": f"{d.isoformat()}T{mm // 60:02d}:{mm % 60:02d}:00+05:30", "o": round(ticks[0], 2),
                    "h": round(max(ticks), 2), "l": round(min(ticks), 2), "c": round(ticks[-1], 2),
                    "v": float(rnd.randint(500, 2500)) * burst, "oi": round(oi)})
        px = ticks[-1]
    return out


def make_synthetic(data_dir: Path, days: int = 48, seed: int = 7, trending: bool = True) -> None:
    rnd = random.Random(seed)
    spot, fut, px, d = [], [], 25000.0, date(2026, 6, 1)
    while len([1 for _ in {b["t"][:10] for b in spot}]) < days:
        if d.weekday() < 5:
            day = synth_day(rnd, d, px, trending)
            px = day[-1]["c"]
            spot += [{**b, "v": 0.0, "oi": 0.0} for b in day]
            fut += [{**b, "o": b["o"] + 12, "h": b["h"] + 12, "l": b["l"] + 12, "c": b["c"] + 12} for b in day]
        d += timedelta(days=1)
    write_csv(data_dir / "NIFTY_spot_1m.csv", spot)
    write_csv(data_dir / "NIFTY_fut_1m.csv", fut)


# ───────────────────────── CLI ─────────────────────────
def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--codes", nargs="+", default=["NIFTY", "BANKNIFTY"])
    common.add_argument("--data-dir", default=str(ROOT / "data" / "backtest"))
    f = sub.add_parser("fetch", parents=[common])
    f.add_argument("--days", type=int, default=120)
    f.add_argument("--start")
    f.add_argument("--to")
    f.add_argument("--chunk-days", type=int, default=20)
    r = sub.add_parser("run", parents=[common])
    r.add_argument("--out-dir", default=str(ROOT / "backtest_out"))
    r.add_argument("--warmup", type=int, default=20, help="trading days used only to build daily levels / ATR")
    r.add_argument("--gate", choices=["off", "legacy", "full"], default="full")
    r.add_argument("--stop-mode", choices=["capped", "chart", "skip"], default="capped")
    r.add_argument("--sweep", action="store_true", help="compare all gate x stop-mode variants on identical signals")
    r.add_argument("--daily-filter", action="store_true", help="only trade with the daily time-series-momentum trend")
    r.add_argument("--no-proxy", action="store_true", help="do not substitute spot-TWAP for missing futures candles")
    r.add_argument("--premium-pct", type=float, default=0.5)
    r.add_argument("--delta", type=float, default=0.5)
    r.add_argument("--min-margin", type=float, default=5.0)
    r.add_argument("--max-margin", type=float, default=10.0)
    r.add_argument("--max-stop", type=float, default=3.5)
    r.add_argument("--theta", type=float, default=1.0)
    r.add_argument("--slip-pct", type=float, default=0.6, help="round-trip slippage as %% of premium")
    r.add_argument("--max-hold", type=int, default=45)
    r.add_argument("--max-trades-day", type=int, default=4)
    r.add_argument("--workers", type=int, default=4)
    sub.add_parser("selftest")
    return p


def main() -> None:
    args = parser().parse_args()
    if args.cmd == "fetch":
        asyncio.run(fetch(args))
    elif args.cmd == "run":
        print(run_backtest(args))
    else:
        # Two synthetic worlds. NULL (zero drift) must show NO edge -- if a variant "wins" there, the harness is biased.
        # TREND (persistent daily drift) must reward trend setups -- if nothing wins there, the harness is blind.
        ok = True
        for label, trending in (("NULL (no edge exists)", False), ("TREND (edge exists by construction)", True)):
            with tempfile.TemporaryDirectory() as td:
                make_synthetic(Path(td), days=88, trending=trending)
                a = parser().parse_args(["run", "--codes", "NIFTY", "--data-dir", td, "--out-dir", td, "--sweep", "--workers", "1"])
                rep = run_backtest(a)
                sec = rep[rep.index("## Variant comparison"):rep.index("## Main variant")]
                print(f"\n##### SELFTEST {label}\n{sec}")
                rows = list(csv.DictReader((Path(td) / "trades.csv").open()))
                gross = sum(float(r["grossPct"]) for r in rows) / len(rows)
                if not trending:
                    good = "KEEP" not in sec and abs(gross + 0.3) < 1.2  # gross ~ -theta (0.3%) when no edge exists
                    print(f"null-world check: avg gross {gross:+.2f}% (expect ~ -0.3% theta), no KEEP rows -> {'PASS' if good else 'FAIL'}")
                else:
                    good = "KEEP" in sec
                    print(f"trend-world check: at least one variant detects the built-in edge -> {'PASS' if good else 'FAIL'}")
                ok = ok and good
        print("\nSELFTEST " + ("OK: harness neither invents nor misses edge (numbers above are synthetic)" if ok else "FAILED"))
        sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
