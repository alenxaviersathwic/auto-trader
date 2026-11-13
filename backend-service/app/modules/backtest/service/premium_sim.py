"""
Option-premium simulation for the backtest module. The underlying's own 1-minute path comes from
REAL Upstox candles (backtest_service.py); Upstox has no historical option-chain API, so there is
no way to replay real premiums for a past date. Every premium here is a Black-Scholes price off
the real underlying path at a FIXED assumed implied volatility -- gamma, real IV changes, and real
bid/ask spreads are not modelled (slippage_pct() stands in for the spread). Treat P&L as an
estimate of what the live engine's rules would have captured, not a real fill.

Mirrors scripts/backtest_day.py's bs()/pick_strike()/run_trade(), adapted to run over any
underlying/date instead of the hand-fetched Yahoo-proxy days that script was written for.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.modules.opportunities.provider.underlying_config import UnderlyingConfig
from app.modules.opportunities.service import menu_builder as mb
from app.modules.opportunities.service.costs import round_trip_cost_pct, slippage_pct

IV: dict[str, float] = {"NIFTY": 0.15, "SENSEX": 0.15, "BANKNIFTY": 0.17, "FINNIFTY": 0.16, "MIDCPNIFTY": 0.18}
DEFAULT_IV = 0.18
MAX_HOLD_MIN = 45
TARGET_DELTA = {"ATM": 0.5, "ITM": 0.65, "OTM": 0.27, "LOTTERY": 0.14}
MIN_YEARS = 1 / (252 * 375)


def _cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def years_left(days_to_expiry: int, minute_of_day: int) -> float:
    """`minute_of_day` is minutes since midnight IST; the session closes at 15:30 (930)."""
    return max(MIN_YEARS, (days_to_expiry * 375 + max(0, 15 * 60 + 30 - minute_of_day)) / (252 * 375))


def bs(spot: float, strike: float, years: float, iv: float, ce: bool) -> tuple[float, float]:
    """(price, |delta|) at zero interest rate -- the live engine's premium estimate for backtests."""
    v = iv * math.sqrt(years)
    if v <= 0 or spot <= 0 or strike <= 0:
        intrinsic = max(0.0, (spot - strike) if ce else (strike - spot))
        return intrinsic, (1.0 if (spot > strike) == ce else 0.0)
    d1 = (math.log(spot / strike) + 0.5 * v * v) / v
    d2 = d1 - v
    if ce:
        return spot * _cdf(d1) - strike * _cdf(d2), _cdf(d1)
    return strike * _cdf(-d2) - spot * _cdf(-d1), _cdf(-d1)


def pick_strike(cfg: UnderlyingConfig, spot: float, days_to_expiry: int, minute: int, ce: bool, mode: str,
                 iv: float) -> tuple[float, float, float] | None:
    """Nearest-to-target-delta strike inside mode's delta band. (strike, premium, |delta|) or None."""
    best = None
    years = years_left(days_to_expiry, minute)
    for k in range(-25, 26):
        strike = (round(spot / cfg.strikeStep) + k) * cfg.strikeStep
        px, d = bs(spot, strike, years, iv, ce)
        lo, hi = mb.DELTA_BANDS[mode]
        if not (lo <= d <= hi) or px < mb.MIN_PREMIUM:
            continue
        score = abs(d - TARGET_DELTA[mode])
        if best is None or score < best[0]:
            best = (score, strike, px, d)
    return (best[1], best[2], best[3]) if best else None


@dataclass
class TradeResult:
    strike: int
    mode: str
    delta: float
    entryPremium: float
    exitPremium: float
    pctMove: float
    outcome: str  # STOP | TARGET | STALLED | NO_NEW_HIGH | TIME | EOD
    entryMinute: int
    exitMinute: int
    exitIdx: int  # index into the `bars` list passed to simulate_trade; the caller's "busy until" marker
    holdMinutes: int
    netPnl: float  # Rs, one lot


def simulate_trade(cfg: UnderlyingConfig, bars: list[dict[str, Any]], entry_idx: int, side: str, target: float,
                    stop: float, atr5: float, mode: str, days_to_expiry: int, bar_minute) -> TradeResult | None:
    """Replays ONE accepted setup forward through `bars` (1-min OHLC dicts) from `entry_idx`, exactly as
    scripts/backtest_day.py::run_trade -- fill at the next bar's open, Black-Scholes premium thereafter,
    the SAME stall-exit / time-stop rules menu_builder.py defines for the live engine."""
    ce = side == "CE"
    sg = 1 if ce else -1
    fill = bars[entry_idx]["o"]
    m0 = bar_minute(bars[entry_idx])
    up, down = (target - fill) * sg, (fill - stop) * sg
    if up <= 0 or down <= 0:
        return None
    iv = IV.get(cfg.code, DEFAULT_IV)
    got = pick_strike(cfg, fill, days_to_expiry, m0, ce, mode, iv)
    if not got:
        return None
    strike, p0, delta = got
    premium_mode = mode in mb.PREMIUM_EXITS
    if premium_mode:
        max_stop, tgt_pct = mb.PREMIUM_EXITS[mode]
        stop_pct = max_stop if mode == "LOTTERY" else max(mb.OTM_MIN_STOP_PCT, min(max_stop, delta * down / p0 * 100))
        tgt_px = p0 * (1 + tgt_pct / 100)
    else:
        stop_pts = min(max(down, mb.STOP_ATR_MIN * atr5), mb.STOP_ATR_MAX * atr5)
        tgt_pts = min(up, mb.TARGET_MAX_R * stop_pts)
        if tgt_pts / stop_pts < 1.2:
            return None
        tgt_px = bs(fill + sg * tgt_pts, strike, years_left(days_to_expiry, m0), iv, ce)[0]

    stall_min = mb.TIME_STOP_MIN.get(mode, 20)
    stall_level = p0 + mb.STALL_PROGRESS_FRAC * (tgt_px - p0)
    out, px, j, peak, peak_j = "TIME", p0, entry_idx, p0, entry_idx
    stalled_at = None
    for j in range(entry_idx, len(bars)):
        b = bars[j]
        m = bar_minute(b)
        years = years_left(days_to_expiry, m)
        fav_s, adv_s = (b["h"], b["l"]) if ce else (b["l"], b["h"])
        p_adv = bs(adv_s, strike, years, iv, ce)[0]
        p_fav = bs(fav_s, strike, years, iv, ce)[0]
        p_c = bs(b["c"], strike, years_left(days_to_expiry, m + 1), iv, ce)[0]
        if premium_mode:
            if p_adv <= p0 * (1 - stop_pct / 100):
                out, px = "STOP", p0 * (1 - stop_pct / 100)
                break
            if p_fav >= tgt_px:
                out, px = "TARGET", tgt_px
                break
        else:
            if (fill - adv_s) * sg >= stop_pts:
                out, px = "STOP", bs(fill - sg * stop_pts, strike, years, iv, ce)[0]
                break
            if (fav_s - fill) * sg >= tgt_pts:
                out, px = "TARGET", tgt_px
                break
        if p_fav > peak:
            peak, peak_j = p_fav, j
        if stalled_at is None and p_fav >= stall_level:
            stalled_at = j
        px = p_c
        if stalled_at is None and j - entry_idx >= stall_min:
            out = "STALLED"
            break
        if j - peak_j >= stall_min + 15:
            out = "NO_NEW_HIGH"
            break
        close_m = bar_minute(bars[-1])
        if m - m0 >= MAX_HOLD_MIN or m >= close_m - 10:
            out = "TIME" if m - m0 >= MAX_HOLD_MIN else "EOD"
            break
    lot = cfg.lotSize
    pct = (px - p0) / p0 * 100
    cost_pct = round_trip_cost_pct(p0, lot, cfg.exchange, max(pct, 0)) + slippage_pct(p0)
    exit_minute = bar_minute(bars[j])
    return TradeResult(strike=int(strike), mode=mode, delta=round(delta, 2), entryPremium=round(p0, 2),
                        exitPremium=round(px, 2), pctMove=round(pct, 1), outcome=out, entryMinute=m0,
                        exitMinute=exit_minute, exitIdx=j, holdMinutes=exit_minute - m0 + 1,
                        netPnl=round((px - p0) * lot - cost_pct / 100 * p0 * lot, 2))


# ───────────────────────── momentum engine (live MOMO policy) ─────────────────────────
TARGET_DELTA["MOMO"] = 0.7


@dataclass
class MomoResult:
    strike: int
    delta: float
    entryPremium: float
    exitPremium: float
    pctMove: float
    outcome: str  # STOP | TRAIL | TIME_EXIT | EOD
    entryMinute: int
    exitMinute: int
    exitIdx: int
    holdMinutes: int
    riskPerLot: float  # Rs between entry premium and the premium at the stop, one lot (session sizing reads this)
    premiumPerLot: float
    netPnl: float


def simulate_momo(cfg: UnderlyingConfig, bars: list[dict[str, Any]], entry_idx: int, side: str, stop: float,
                  atr5: float, days_to_expiry: int, bar_minute, fixed_stop: bool = False,
                  exit_by_min: int | None = None, close_min: int | None = None) -> MomoResult | None:
    """The live momentum exit (menu_builder.MOMO_EXIT, trader_brain momentum_trail) over the real underlying path:
    ITM next-expiry strike (delta 0.6-0.8), stop = chart stop clamped to 0.5-1.25 x ATR5 (FII_OPEN_DRIVE keeps its
    own fixed stop), breakeven at +beR R, trail trailR R under the best move from +fromR R, no fixed target,
    square-off 10 min before close or at `exit_by_min` (strategy time exit). Black-Scholes premiums at fixed IV."""
    if entry_idx >= len(bars):
        return None
    ce = side == "CE"
    sg = 1 if ce else -1
    fill = bars[entry_idx]["o"]
    m0 = bar_minute(bars[entry_idx])
    down = (fill - stop) * sg
    if down <= 0:
        return None
    iv = IV.get(cfg.code, DEFAULT_IV)
    got = pick_strike(cfg, fill, days_to_expiry, m0, ce, "MOMO", iv)
    if not got:
        return None
    strike, p0, delta = got
    stop_pts = down if fixed_stop or atr5 <= 0 else min(max(down, mb.STOP_ATR_MIN * atr5), mb.STOP_ATR_MAX * atr5)
    ex = mb.MOMO_EXIT
    risk_lot = max(0.0, p0 - bs(fill - sg * stop_pts, strike, years_left(days_to_expiry, m0), iv, ce)[0]) * cfg.lotSize
    close_m = close_min if close_min is not None else bar_minute(bars[-1])
    line, best, out, px, j = -stop_pts, 0.0, "EOD", p0, entry_idx
    for j in range(entry_idx, len(bars)):
        b = bars[j]
        m = bar_minute(b)
        years = years_left(days_to_expiry, m)
        fav, adv = (b["h"], b["l"]) if ce else (b["l"], b["h"])
        if (adv - fill) * sg <= line:
            out = "STOP" if line < 0 else "TRAIL"
            px = bs(fill + sg * line, strike, years, iv, ce)[0]
            break
        best = max(best, (fav - fill) * sg)
        if best >= ex["beR"] * stop_pts:
            line = max(line, 0.0)
        if best >= ex["fromR"] * stop_pts:
            line = max(line, best - ex["trailR"] * stop_pts)
        px = bs(b["c"], strike, years_left(days_to_expiry, m + 1), iv, ce)[0]
        if exit_by_min is not None and m >= exit_by_min:
            out = "TIME_EXIT"
            break
        if m >= close_m - 10:
            out = "EOD"
            break
    lot = cfg.lotSize
    pct = (px - p0) / p0 * 100
    cost_pct = round_trip_cost_pct(p0, lot, cfg.exchange, max(pct, 0)) + slippage_pct(p0)
    exit_minute = bar_minute(bars[j])
    return MomoResult(strike=int(strike), delta=round(delta, 2), entryPremium=round(p0, 2), exitPremium=round(px, 2),
                      pctMove=round(pct, 1), outcome=out, entryMinute=m0, exitMinute=exit_minute, exitIdx=j,
                      holdMinutes=exit_minute - m0 + 1, riskPerLot=round(risk_lot, 2),
                      premiumPerLot=round(p0 * lot, 2),
                      netPnl=round((px - p0) * lot - cost_pct / 100 * p0 * lot, 2))
