#!/usr/bin/env python3
"""One-day replay of the LIVE entry rules on 1-minute candles (default data: 9 Nov 2026), P&L in Rs per lot.

Same engine code as live: analyze -> detect -> confirm_timeframes (day-type gate + timeframes) -> guardrails ->
strike_mode -> exits as in menu_builder. There are no historical option prices here, so every premium is a
Black-Scholes price from the index path at a FIXED implied volatility (IV, below): theta and gamma are modelled,
IV changes and real spreads are not (slippage_pct() stands in for the spread). Treat rupees as an estimate.

  PYTHONPATH=. python scripts/backtest_day.py
"""
from __future__ import annotations

import csv
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
NEXT_EXPIRY_9NOV = {"NIFTY": "2026-11-17"}
IV = {"NIFTY": 0.15, "SENSEX": 0.15, "BANKNIFTY": 0.17}  # assumption
MAX_HOLD = 45
TARGET_DELTA = {"ATM": 0.5, "ITM": 0.65, "OTM": 0.27, "LOTTERY": 0.14, "MOMO": 0.7}
NEXT_EXPIRY: dict[str, str] = dict(NEXT_EXPIRY_9NOV)  # series MOMO trades when EXPIRY[code] == DAY (it never buys the expiring series)
MOMO_TRAIL_ATR = 1.0  # MOMO exit: breakeven after +MOMO_BE_R, then trail the best move by MOMO_TRAIL_ATR x ATR5
MOMO_BE_R = mb.MOMO_EXIT["beR"]  # live policy (menu_builder.MOMO_EXIT): breakeven at +1.5R,
MOMO_TRAIL_FROM_R = mb.MOMO_EXIT["fromR"]  # trail from +2R,
MOMO_TRAIL_R = mb.MOMO_EXIT["trailR"]  # 2R under the best move; set None to trail by MOMO_TRAIL_ATR x ATR5 instead
MOMO_TARGET_R = 99.0  # no fixed target for the momentum engine (live trader never exits MOMO at a target)
SCALP: dict | None = None  # research: {"tgtR": 1.0, "stall": 10, "hold": 20} = fixed-R scalp exit instead of the MOMO trail
V3_EXITS: set[str] = set()  # "TIME_STOP", "LOSERS_1500", "LATE_TIGHTEN" (menu_builder.MOMO_V3_EXITS mirrors live)
EXTRA_A = None  # optional (code, day, minute, cand) -> extra analysis fields (vix, oiBuildupDaily, heavyweights)
MAX_PER_DAY = None  # override guardrails.MAX_PER_DAY in replays (None = live default)
MAX_PER_SETUP = None
_exp: dict[str, str] = {}


def _expiry(code: str) -> str:
    return _exp.get(code) or EXPIRY[code]
MIN_YEARS = 1 / (252 * 375)
# Real option prices (research gap 2): when 1-minute candles for the traded contract exist here, the trade is priced
# from them (entry at the bar open + half the measured/assumed spread, exits on real highs/lows) instead of
# Black-Scholes at a fixed IV. Fill them with scripts/fetch_day_option_candles.py (same day) or
# scripts/backfill_expired_options.py (expired series).
DATA_DIR = Path(__file__).resolve().parents[1] / "backtest_data"
REAL_HALF_SPREAD_PCT = 0.25  # paid on entry and exit when the data has no bid/ask
_real_cache: dict[tuple, dict[int, dict] | None] = {}


def real_bars(code: str, strike: float, ce: bool) -> dict[int, dict] | None:
    """{minute-of-day: {o,h,l,c}} for DAY from backtest_data, or None when not downloaded."""
    exp = _expiry(code)
    key = (DAY, code, exp, int(strike), ce)
    if key in _real_cache:
        return _real_cache[key]
    name = f"{int(strike)}{'CE' if ce else 'PE'}.csv"
    out = None
    for f in (DATA_DIR / "options" / DAY / code / name, DATA_DIR / "expired" / code / exp / name):
        if f.exists():
            out = {}
            with open(f, newline="") as fh:
                for r in csv.DictReader(fh):
                    ts = r["ts"]
                    if not ts.startswith(DAY):
                        continue
                    m = int(ts[11:13]) * 60 + int(ts[14:16])
                    out[m] = {"o": float(r["open"]), "h": float(r["high"]), "l": float(r["low"]), "c": float(r["close"])}
            out = out or None
            break
    _real_cache[key] = out
    return out


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
    days = (datetime.fromisoformat(_expiry(code)) - datetime.fromisoformat(DAY)).days
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
    if mode == "MOMO" and EXPIRY[code] == DAY:
        if not NEXT_EXPIRY.get(code):
            return None
        _exp[code] = NEXT_EXPIRY[code]
    try:
        r = _run_trade(code, bars, k, s, atr5, mode)
        if r:
            r = _apply_real(code, r, s["side"] == "CE")
    finally:
        _exp.pop(code, None)
    if r and mode == "MOMO" and EXPIRY[code] == DAY:
        r["mode"] = "MOMO>"  # priced on the next expiry
    return r


def _run_trade(code, bars, k, s, atr5, mode):
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
        tgt_pts = MOMO_TARGET_R * stop_pts if mode == "MOMO" else min(up, mb.TARGET_MAX_R * stop_pts)
        if tgt_pts / stop_pts < 1.2:
            return None
    momo = mode == "MOMO"
    if SCALP and momo:
        momo, tgt_pts = False, SCALP["tgtR"] * stop_pts
    stop_line = -stop_pts if not premium else None  # MOMO: points from fill; ratchets up, never down
    best = 0.0
    close_m = bt._mins(cfg.close_today(datetime.fromisoformat(DAY).replace(tzinfo=IST)))
    stall_min = SCALP["stall"] if SCALP and mode == "MOMO" else mb.TIME_STOP_MIN.get(mode, 20)
    max_hold = SCALP["hold"] if SCALP and mode == "MOMO" else MAX_HOLD
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
        elif momo:
            if (adv_s - fill) * sg <= stop_line:
                out = "STOP" if stop_line < 0 else "TRAIL"
                px = bs(code, fill + sg * stop_line, strike, m, ce)[0]
                break
            if (fav_s - fill) * sg >= tgt_pts:
                out, px = "TARGET", tgt_px
                break
            best = max(best, (fav_s - fill) * sg)
            if best >= MOMO_BE_R * stop_pts:
                stop_line = max(stop_line, 0.0)
            if best >= MOMO_TRAIL_FROM_R * stop_pts:
                trail = MOMO_TRAIL_R * stop_pts if MOMO_TRAIL_R else MOMO_TRAIL_ATR * atr5
                if "LATE_TIGHTEN" in V3_EXITS and m >= 14 * 60 + 30:
                    trail = min(trail, 1.25 * stop_pts)
                stop_line = max(stop_line, best - trail)
            held = m - m0
            if "TIME_STOP" in V3_EXITS and ((held >= 30 and best < 0.5 * stop_pts) or (held >= 75 and best < stop_pts)):
                out, px = "TSTOP", bs(code, b["c"], strike, m + 1, ce)[0]
                break
            if "LOSERS_1500" in V3_EXITS and m >= close_m - (40 if cfg.exchange == "NSE" and close_m >= 15 * 60 + 40 else 30) \
                    and stop_line < 0:
                out, px = "EXIT1500", bs(code, b["c"], strike, m + 1, ce)[0]
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
        if momo:
            if m >= close_m - 10:
                out = "EOD"
                break
            continue
        if stalled_at is None and j - k >= stall_min:
            out = "STALLED"
            break
        if j - peak_j >= stall_min + 15:  # gave back a favourable move and went quiet again
            out = "NO_NEW_HIGH"
            break
        if m - m0 >= max_hold or m >= close_m - 10:
            out = "TIME" if m - m0 >= max_hold else "EOD"
            break
    lot = cfg.lotSize
    pct = (px - p0) / p0 * 100
    cost_pct = round_trip_cost_pct(p0, lot, cfg.exchange, max(pct, 0)) + slippage_pct(p0)
    return {"fees": cost_pct / 100 * p0 * lot, "exitK": j, "exitMin": bt._bar_min(bars[j]["t"]), "out": out, "strike": int(strike), "mode": mode, "p0": p0, "px": px,
            "delta": delta, "pct": pct, "hold": bt._bar_min(bars[j]["t"]) - m0 + 1, "net": (px - p0) * lot - cost_pct / 100 * p0 * lot,
            "lot": lot}


def _apply_real(code, r, ce):
    """Re-price a trade from REAL option candles: the entry / exit decisions stay those of the replay (made on the
    real index path), the rupees come from the contract's actual 1-minute prices -- entry at the entry minute's open,
    exit at the exit minute's close (stop / target bars use the level when the real bar traded through it), both
    with REAL_HALF_SPREAD_PCT paid. No real candle at either minute -> the trade stays model-priced (no '*')."""
    rb = real_bars(code, r["strike"], ce)
    m0 = r["exitMin"] - r["hold"] + 1
    if not rb or m0 not in rb or r["exitMin"] not in rb:
        r["real"] = False
        return r
    cfg = get_config(code)
    p0 = rb[m0]["o"] * (1 + REAL_HALF_SPREAD_PCT / 100)
    xb = rb[r["exitMin"]]
    px = xb["c"]
    lot = cfg.lotSize
    px *= 1 - REAL_HALF_SPREAD_PCT / 100
    pct = (px - p0) / p0 * 100
    cost_pct = round_trip_cost_pct(p0, lot, cfg.exchange, max(pct, 0))
    spread_rs = (rb[m0]["o"] + xb["c"]) * REAL_HALF_SPREAD_PCT / 100 * lot
    r.update({"p0": p0, "px": px, "pct": pct, "mode": r["mode"] + "*", "real": True,
              "fees": cost_pct / 100 * p0 * lot + spread_rs,
              "net": (px - p0) * lot - cost_pct / 100 * p0 * lot})
    return r


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
             "dayBias": cd.get("dayBias"), "levels": cd.get("levels"), "code": code, "noise": cd.get("noise"),
             "spot": cd["bars1"][-1]["c"] if cd.get("bars1") else None}
        if EXTRA_A:
            a.update(EXTRA_A(code, DAY, m, cd) or {})
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
        kw = {k: v for k, v in (("max_per_day", MAX_PER_DAY), ("max_per_setup", MAX_PER_SETUP)) if v is not None}
        kept, why = guardrails.apply(today, [{"side": s["side"], "setup": s["name"], "s": s} for s in ok], now, **kw)
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
    print("(mode marked * = priced from REAL option candles in backtest_data/; otherwise Black-Scholes at fixed IV)")


if __name__ == "__main__":
    main()
