#!/usr/bin/env python3
"""One-day replay of the LIVE entry rules on 1-minute candles (default data: 9 Nov 2026), P&L in Rs per lot.

Same engine code as live: analyze -> detect -> confirm_timeframes (day-type gate + timeframes) -> guardrails ->
strike_mode -> exits as in menu_builder. There are no historical option prices here, so every premium is a
Black-Scholes price from the index path at a FIXED implied volatility (IV, below): theta and gamma are modelled,
IV changes and real spreads are not (slippage_pct() stands in for the spread). Treat rupees as an estimate.

  PYTHONPATH=. python scripts/backtest_day.py
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest_setups as bt  # noqa: E402
import day_data as dd  # noqa: E402
from app.modules.opportunities.provider.underlying_config import get_config  # noqa: E402
from app.modules.opportunities.service import guardrails, menu_builder as mb, setups as su  # noqa: E402
from app.modules.opportunities.service.costs import round_trip_cost_pct, slippage_pct  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
DAY = "2026-11-09"
# expiry of the series the engine would trade that day (NIFTY: Tuesday 10 Nov was a holiday -> expired Monday 9 Nov)
EXPIRY = {"NIFTY": "2026-11-09", "SENSEX": "2026-11-12", "BANKNIFTY": "2026-11-23"}
IV = {"NIFTY": 0.15, "SENSEX": 0.15, "BANKNIFTY": 0.17}  # assumption
MAX_HOLD = 45
TARGET_DELTA = {"ATM": 0.5, "ITM": 0.65, "OTM": 0.27, "LOTTERY": 0.14}
MIN_YEARS = 1 / (252 * 375)


def decode(s: str, day: str) -> list[dict]:
    parts = s.split("|")
    p = int(parts[0]) / 100
    out = []
    t0 = datetime.fromisoformat(day + "T09:15:00").replace(tzinfo=IST)
    for i, row in enumerate(("|".join(parts[2:])).split(";")):
        o, h, l, c = (p + int(x, 36) / 100 for x in row.split(","))
        out.append({"t": (t0 + timedelta(minutes=i)).isoformat(), "o": o, "h": max(h, o, c), "l": min(l, o, c), "c": c,
                    "v": 1.0, "oi": 0.0})
        p = c
    return out


def daily_bars(rows):
    return [{"t": f"{r[0]}T09:15:00+05:30", "o": r[1], "h": r[2], "l": r[3], "c": r[4], "v": 1.0, "oi": 0.0} for r in rows]


def _cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def years_left(code: str, minute: int) -> float:
    days = (datetime.fromisoformat(EXPIRY[code]) - datetime.fromisoformat(DAY)).days
    return max(MIN_YEARS, (days * 375 + max(0, 15 * 60 + 30 - minute)) / (252 * 375))


def bs(code: str, spot: float, strike: float, minute: int, ce: bool) -> tuple[float, float]:
    """(price, |delta|), zero rates."""
    t = years_left(code, minute)
    v = IV[code] * math.sqrt(t)
    d1 = (math.log(spot / strike) + 0.5 * v * v) / v
    d2 = d1 - v
    if ce:
        return spot * _cdf(d1) - strike * _cdf(d2), _cdf(d1)
    return strike * _cdf(-d2) - spot * _cdf(-d1), _cdf(-d1)


def pick_strike(code, spot, minute, ce, mode):
    cfg = get_config(code)
    best = None
    for k in range(-25, 26):
        strike = (round(spot / cfg.strikeStep) + k) * cfg.strikeStep
        px, d = bs(code, spot, strike, minute, ce)
        lo, hi = mb.DELTA_BANDS[mode]
        if not (lo <= d <= hi) or px < mb.MIN_PREMIUM:
            continue
        score = abs(d - TARGET_DELTA[mode])
        if best is None or score < best[0]:
            best = (score, strike, px, d)
    return best[1:] if best else None


def run_trade(code, bars, k, s, atr5, mode):
    cfg = get_config(code)
    ce = s["side"] == "CE"
    sg = 1 if ce else -1
    fill = bars[k]["o"]
    m0 = bt._bar_min(bars[k]["t"])
    up, down = (s["target"] - fill) * sg, (fill - s["stop"]) * sg
    if up <= 0 or down <= 0:
        return None
    got = pick_strike(code, fill, m0, ce, mode)
    if not got:
        return None
    strike, p0, delta = got
    premium = mode in mb.PREMIUM_EXITS
    if premium:
        max_stop, tgt_pct = mb.PREMIUM_EXITS[mode]
        stop_pct = max_stop if mode == "LOTTERY" else max(mb.OTM_MIN_STOP_PCT, min(max_stop, delta * down / p0 * 100))
    else:
        stop_atr_max = mb.STOP_ATR_MAX_REVERSAL if s.get("family") == "REVERSAL" else mb.STOP_ATR_MAX
        stop_pts = min(max(down, mb.STOP_ATR_MIN * atr5), stop_atr_max * atr5)
        tgt_pts = min(up, mb.TARGET_MAX_R * stop_pts)
        if tgt_pts / stop_pts < 1.2:
            return None
    close_m = bt._mins(cfg.close_today())
    stall_min = mb.TIME_STOP_MIN.get(mode, 20)
    tgt_px = p0 * (1 + tgt_pct / 100) if premium else bs(code, fill + sg * tgt_pts, strike, m0, ce)[0]
    stall_level = p0 + mb.STALL_PROGRESS_FRAC * (tgt_px - p0)
    out, px, j, peak, peak_j, stalled_at = "TIME", p0, k, p0, k, None
    for j in range(k, len(bars)):
        b = bars[j]
        m = bt._bar_min(b["t"])
        fav_s, adv_s = (b["h"], b["l"]) if ce else (b["l"], b["h"])
        p_adv, p_fav, p_c = bs(code, adv_s, strike, m, ce)[0], bs(code, fav_s, strike, m, ce)[0], bs(code, b["c"], strike, m + 1, ce)[0]
        if premium:
            if p_adv <= p0 * (1 - stop_pct / 100):
                out, px = "STOP", p0 * (1 - stop_pct / 100)
                break
            if p_fav >= tgt_px:
                out, px = "TARGET", tgt_px
                break
        else:
            if (fill - adv_s) * sg >= stop_pts:
                out, px = "STOP", bs(code, fill - sg * stop_pts, strike, m, ce)[0]
                break
            if (fav_s - fill) * sg >= tgt_pts:
                out, px = "TARGET", tgt_px
                break
        if p_fav > peak:
            peak, peak_j = p_fav, j
        if stalled_at is None and p_fav >= stall_level:
            stalled_at = j  # reached 25% of the way to target at least once: no longer a stall candidate
        px = p_c
        if stalled_at is None and j - k >= stall_min:
            out = "STALLED"
            break
        if j - peak_j >= stall_min + 15:  # gave back a favourable move and went quiet again
            out = "NO_NEW_HIGH"
            break
        if m - m0 >= MAX_HOLD or m >= close_m - 10:
            out = "TIME" if m - m0 >= MAX_HOLD else "EOD"
            break
    lot = cfg.lotSize
    pct = (px - p0) / p0 * 100
    cost_pct = round_trip_cost_pct(p0, lot, cfg.exchange, max(pct, 0)) + slippage_pct(p0)
    return {"exitK": j, "exitMin": bt._bar_min(bars[j]["t"]), "out": out, "strike": int(strike), "mode": mode, "p0": p0, "px": px,
            "delta": delta, "pct": pct, "hold": bt._bar_min(bars[j]["t"]) - m0 + 1, "net": (px - p0) * lot - cost_pct / 100 * p0 * lot,
            "lot": lot}


class _Row:  # what guardrails.apply reads from a saved opportunity
    def __init__(self, side, created, outcome, resolved):
        self.optionType, self.createdAt, self.outcome, self.resolvedAt = side, created, outcome, resolved
        self.strategy = None


def _dt(minute: int) -> datetime:
    return datetime.fromisoformat(DAY).replace(hour=minute // 60, minute=minute % 60, tzinfo=IST)


def replay(code, cands, bars):
    trades, rows, busy = [], [], -1
    seen = {"fired": 0, "dayType": 0, "timeframes": 0, "guardrail": 0, "guardrailWhy": []}
    for cd in cands:
        k, m = cd["k"], cd["m"]
        if k <= busy:
            continue
        a = {"trend15": cd["trend15"], "bars1": cd["bars1"], "atr5": cd["atr5"], "dayType": cd.get("dayType"),
             "dayBias": cd.get("dayBias")}
        ok, rejected = su.confirm_timeframes(a, cd["raw"])
        seen["fired"] += len(cd["raw"])
        seen["dayType"] += sum(1 for r in rejected if " day" in r["reason"] or "bias" in r["reason"])
        seen["timeframes"] += sum(1 for r in rejected if " day" not in r["reason"] and "bias" not in r["reason"])
        if not ok:
            continue
        now = _dt(m)
        today = [r for r in rows if r.resolvedAt is None or r.resolvedAt <= now or True]
        for r in today:  # outcomes only become visible once resolved
            r.outcome = r._final if r._until <= now else "PENDING"
        kept, why = guardrails.apply(today, [{"side": s["side"], "setup": s["name"], "s": s} for s in ok], now)
        if not kept:
            seen["guardrail"] += 1
            if why:
                seen["guardrailWhy"].append(f"{m // 60:02d}:{m % 60:02d} {why}")
            continue
        for pk in sorted(kept, key=lambda p: -p["s"].get("strength", 0)):
            s = pk["s"]
            mode = mb.strike_mode({"dayType": cd.get("dayType"), "dte": (datetime.fromisoformat(EXPIRY[code]) - datetime.fromisoformat(DAY)).days},
                                  s, now)
            r = run_trade(code, bars, k, s, cd["atr5"], mode)
            if r is None:
                continue
            busy = r["exitK"]
            row = _Row(s["side"], now, "PENDING", _dt(r["exitMin"]))
            row._final = "STOP_HIT" if r["out"] == "STOP" else "TARGET_HIT" if r["out"] == "TARGET" else "EXPIRED"
            row._until = _dt(r["exitMin"])
            row.strategy = s["name"]
            rows.append(row)
            trades.append({"time": f"{m // 60:02d}:{m % 60:02d}", "setup": s["name"], "side": s["side"],
                           "dayType": (cd.get("dayType") or {}).get("type"), **r})
            break
    return trades, seen


def main() -> None:
    data = {"NIFTY": dd.NIFTY, "BANKNIFTY": dd.BANKNIFTY, "SENSEX": dd.SENSEX}
    total_n = total = 0
    for code, s in data.items():
        bars = decode(s, DAY)
        cands = bt.scan(code, {DAY: bars}, {}, 0, True, seed_daily=daily_bars(dd.DAILY[code]))
        tl, prev = [], None
        for cd in cands:
            t = (cd.get("dayType") or {}).get("type")
            if t != prev:
                tl.append(f"{cd['m'] // 60:02d}:{cd['m'] % 60:02d} {t}")
                prev = t
        trades, seen = replay(code, cands, bars)
        net = sum(t["net"] for t in trades)
        total_n, total = total_n + len(trades), total + net
        print(f"\n=== {code} (lot {get_config(code).lotSize}, expiry {EXPIRY[code]}, IV {IV[code]:.0%}): {len(trades)} opportunities, "
              f"net Rs {net:+,.0f} per lot")
        print(f"  day type when setups fired: {' -> '.join(tl)}")
        print(f"  setups fired {seen['fired']} | blocked by day type {seen['dayType']} | by timeframes {seen['timeframes']} | "
              f"guardrail holds {seen['guardrail']}")
        for w in seen["guardrailWhy"]:
            print(f"    held: {w}")
        for t in trades:
            print(f"  {t['time']} {t['setup']:<21}{t['side']} {t['dayType']:<9} {t['strike']} {t['mode']:<7} d={t['delta']:.2f} "
                  f"Rs {t['p0']:.2f} -> {t['px']:.2f} ({t['pct']:+.0f}%) {t['out']:<11} {t['hold']}m  net Rs {t['net']:+,.0f}")
    print(f"\nTOTAL: {total_n} opportunities, net Rs {total:+,.0f} for one lot of each")


if __name__ == "__main__":
    main()
