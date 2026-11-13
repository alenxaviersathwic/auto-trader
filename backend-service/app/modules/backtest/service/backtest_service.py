"""
On-demand backtest: pick dates on a calendar + pick indices, run the SAME engine code the live
opportunities loop runs (market_analysis.analyze -> setups.detect -> setups.confirm_timeframes ->
guardrails.apply -> menu_builder.strike_mode) over REAL Upstox 1-minute candles for each date, and
report how many opportunities fired, how many won, how many lost, and the net P&L per lot.

What this is NOT: a replay of real option prices. Upstox has no historical option-chain API, so
every premium is a Black-Scholes estimate off the real underlying path (premium_sim.py) at a fixed
assumed IV. The underlying price path and every entry rule are real; the premium and P&L are an
estimate. Needs a configured Upstox token (the same one the live engine uses) -- without it every
date/index comes back with an error instead of silently inventing numbers.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.backtest.service import expiry_calendar, premium_sim
from app.modules.opportunities.provider.underlying_config import get_config
from app.modules.opportunities.provider.upstox_market_data import market_data
from app.modules.opportunities.service import day_type, guardrails
from app.modules.opportunities.service import menu_builder as mb
from app.modules.opportunities.service import setups as setup_detector
from app.modules.opportunities.service.market_analysis import _bar_min, _mins, analyze

IST = ZoneInfo("Asia/Kolkata")
HISTORY_LOOKBACK_DAYS = 25  # calendar days fetched before the target date, for the daily-ATR proxy
WARMUP_MIN = 6  # mirrors scripts/backtest_setups.py: skip the first few minutes, last 20 (0-DTE cutoff zone)
TAIL_MIN = 20


class _Row:
    """What guardrails.apply() reads off a saved opportunity -- a stand-in for the real DB row."""

    def __init__(self, side: str, created: datetime, until: datetime, final: str, strategy: str) -> None:
        self.optionType, self.createdAt, self.outcome, self.resolvedAt = side, created, "PENDING", until
        self.strategy = strategy
        self._final, self._until = final, until


def _day_bar(bars: list[dict[str, Any]]) -> dict[str, Any]:
    return {"t": bars[0]["t"], "o": bars[0]["o"], "h": max(b["h"] for b in bars), "l": min(b["l"] for b in bars),
            "c": bars[-1]["c"], "v": sum(b["v"] for b in bars), "oi": bars[-1]["oi"]}


def _by_day(bars: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in sorted(bars, key=lambda x: x["t"]):
        out[b["t"][:10]].append(b)
    return dict(out)


async def _one(code: str, day: str, session: AsyncSession) -> dict[str, Any]:
    cfg = get_config(code)
    if not cfg:
        return {"date": day, "code": code, "error": f"{code}: not a configured underlying"}
    if not cfg.instrumentKey:
        return {"date": day, "code": code, "error": f"{code}: no Upstox instrument key configured"}
    as_of = date.fromisoformat(day)
    expiry = expiry_calendar.expiry_for(code, as_of)
    if not expiry:
        return {"date": day, "code": code, "error": f"{code}: could not work out the live expiry for this date"}
    from_date = (as_of - timedelta(days=HISTORY_LOOKBACK_DAYS)).isoformat()
    try:
        bars = await market_data.candles_1m_range(cfg.instrumentKey, from_date, day, session)
    except Exception as e:  # no token / Upstox unreachable / bad date range
        return {"date": day, "code": code, "error": f"couldn't fetch Upstox candles: {type(e).__name__}: {e}"}
    by_day = _by_day(bars)
    today_bars = by_day.get(day)
    if not today_bars or len(today_bars) < 30:
        return {"date": day, "code": code,
                "error": "no Upstox candle data for this date (market holiday, date too old for the API, "
                         "or no token/DB configured)"}
    daily_seed = [_day_bar(by_day[d]) for d in sorted(by_day) if d < day]
    dte = (expiry - as_of).days

    open_m, close_m = _mins(cfg.open), _mins(cfg.close)
    cands: list[dict[str, Any]] = []
    daily = list(daily_seed)
    bias_state: dict[str, Any] = {}
    for k in range(1, len(today_bars)):
        m = _bar_min(today_bars[k]["t"])
        if m < open_m + WARMUP_MIN:
            continue
        if m > close_m - TAIL_MIN:
            break
        market = {"spot": today_bars[k - 1]["c"], "spotBars1m": today_bars[:k], "futBars1m": [],
                  "daily": daily, "chains": [], "vix": None}
        a = analyze(cfg, market, datetime(as_of.year, as_of.month, as_of.day, m // 60, m % 60, tzinfo=IST))
        if a["session"]["blocked"]:
            continue
        bias_state = day_type.apply_bias(a.get("dayType") or {}, bias_state, m)
        raw = setup_detector.detect(a, cfg)
        if raw:
            cands.append({"k": k, "m": m, "raw": raw, "trend15": a.get("trend15"), "atr5": a.get("atr5") or 0.0,
                          "bars1": a["bars1"][-30:], "dayType": a.get("dayType"), "dayBias": bias_state.get("bias"),
                          "levels": dict(a.get("levels") or {})})

    trades: list[dict[str, Any]] = []
    rows: list[_Row] = []
    busy = -1
    held_back = 0
    for cd in cands:
        k, m = cd["k"], cd["m"]
        if k <= busy:
            continue
        a_gate = {"trend15": cd["trend15"], "bars1": cd["bars1"], "atr5": cd["atr5"], "dayType": cd["dayType"],
                  "dayBias": cd["dayBias"], "levels": cd.get("levels")}
        ok, _rejected = setup_detector.confirm_timeframes(a_gate, cd["raw"])
        if not ok:
            continue
        now = datetime(as_of.year, as_of.month, as_of.day, m // 60, m % 60, tzinfo=IST)
        for r in rows:
            r.outcome = r._final if r._until <= now else "PENDING"
        kept, _why = guardrails.apply(rows, [{"side": s["side"], "setup": s["name"], "s": s} for s in ok], now)
        if not kept:
            held_back += 1
            continue
        for pk in sorted(kept, key=lambda p: -p["s"].get("strength", 0)):
            s = pk["s"]
            mode = mb.strike_mode({"dayType": cd["dayType"], "dte": dte}, s, now)
            tr = premium_sim.simulate_trade(cfg, today_bars, k, s["side"], s["target"], s["stop"], cd["atr5"],
                                             mode, dte, lambda b: _bar_min(b["t"]))
            if tr is None:
                continue
            busy = tr.exitIdx
            exit_dt = datetime(as_of.year, as_of.month, as_of.day, tr.exitMinute // 60, tr.exitMinute % 60, tzinfo=IST)
            final = "STOP_HIT" if tr.outcome == "STOP" else "TARGET_HIT" if tr.outcome == "TARGET" else "EXPIRED"
            rows.append(_Row(s["side"], now, exit_dt, final, s["name"]))
            trades.append({"time": f"{m // 60:02d}:{m % 60:02d}", "setup": s["name"], "side": s["side"],
                           "dayType": (cd["dayType"] or {}).get("type"), "strike": tr.strike, "mode": tr.mode,
                           "delta": tr.delta, "entryPremium": tr.entryPremium, "exitPremium": tr.exitPremium,
                           "pctMove": tr.pctMove, "outcome": tr.outcome, "holdMinutes": tr.holdMinutes,
                           "netPnl": tr.netPnl})
            break

    wins = sum(1 for t in trades if t["netPnl"] > 0)
    losses = sum(1 for t in trades if t["netPnl"] <= 0)
    net = round(sum(t["netPnl"] for t in trades), 2)
    return {"date": day, "code": code, "lotSize": cfg.lotSize, "expiry": expiry.isoformat(), "dte": dte,
            "opportunities": len(trades), "wins": wins, "losses": losses,
            "winRatePct": round(wins / len(trades) * 100, 1) if trades else None,
            "netPnl": net, "heldBackByGuardrails": held_back, "trades": trades}


async def run(dates: list[str], codes: list[str], session: AsyncSession) -> dict[str, Any]:
    results = [await _one(code, day, session) for day in sorted(set(dates)) for code in codes]
    ok = [r for r in results if "error" not in r]
    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in ok:
        by_code[r["code"]].append(r)
    per_code = [
        {"code": code, "opportunities": sum(r["opportunities"] for r in rs), "wins": sum(r["wins"] for r in rs),
         "losses": sum(r["losses"] for r in rs),
         "winRatePct": round(sum(r["wins"] for r in rs) / sum(r["opportunities"] for r in rs) * 100, 1)
         if sum(r["opportunities"] for r in rs) else None,
         "netPnl": round(sum(r["netPnl"] for r in rs), 2), "daysRun": len(rs)}
        for code, rs in sorted(by_code.items())
    ]
    total_opps = sum(r["opportunities"] for r in ok)
    total_wins = sum(r["wins"] for r in ok)
    return {
        "runs": results,
        "perIndex": per_code,
        "totals": {
            "opportunities": total_opps, "wins": total_wins, "losses": sum(r["losses"] for r in ok),
            "winRatePct": round(total_wins / total_opps * 100, 1) if total_opps else None,
            "netPnl": round(sum(r["netPnl"] for r in ok), 2),
            "datesRun": len(set(dates)), "indicesRun": len(codes), "errors": len(results) - len(ok),
        },
    }
