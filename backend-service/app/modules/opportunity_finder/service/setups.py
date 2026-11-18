"""
Intraday setups detected in CODE on completed 5-minute bars (repeatable, measurable, no LLM guessing).

Every setup returns the underlying-price plan a trader draws on the chart:
    entry (last close), stop (invalidation level), target (next key level, else 2R)
and the menu turns that plan into an option premium target/stop through the contract's delta.

  ORB              opening-range (first 15 min) breakout on a volume spike         not in RANGE regime
  VWAP_PULLBACK    15-min trend + pullback to futures VWAP that is bought/sold       TREND / MIXED
  PDH_PDL_RETEST   previous-day high (low) broken earlier, retested, holding        any regime
  CPR_BREAKOUT     narrow-CPR day, fresh close outside the CPR                      any regime
  OI_WALL_REJECT   rejection wick at the highest-OI call (put) strike               RANGE / MIXED
  MOMENTUM_FLAG    impulse (>= 2 ATR) -> tight pause in the top half -> break of it  not in RANGE regime
  EMA_CROSS_RETEST 5-min EMA 9/21 cross, pullback to the EMAs holds, resumes          TREND / MIXED
  SUPERTREND_FLIP  5-min Supertrend(10,3) flips on the last bar                        not in RANGE regime
  SUPERTREND_RETEST  after a flip, price retests the Supertrend line and holds         TREND / MIXED
  INSIDE_BAR       inside bar (vs its mother bar) broken on a close                    any regime
  RANGE_BREAKOUT   tight multi-bar consolidation broken on a close                    any regime
  GAP_GO           0.5-2% gap holds, close > open & VWAP, >=75% of bars on the gap side,  09:30-10:45
                   within 0.4% of VWAP (not chasing)
  PCR_SHIFT        DEMOTED 10 Nov 2026 (see below) -- no longer an independent setup, confluence only
  SHORT_COVERING_SPIKE  futures price up + OI down + volume spike (mirror: long unwinding)  any regime
  FAILED_BREAK_RECLAIM  a key level (OR low/high, PDL/PDH, S1/R1, BC/TC, pivot, OI strike) broken by >= 0.1 ATR,
                   then a 5-min close back through it: the trapped side's stops fuel the move   any regime
                   (also covers the opening-range fade: a failed first break of the OR)
  VWAP_BAND_REVERT stretch beyond futures VWAP +/- 2 SD, 5-min close back inside, VWAP flat  RANGE / MIXED
  NOISE_BREAKOUT   first 5-min close outside the noise area (Zarattini et al. 2024): the move is no longer noise
  LATE_DAY_MOMENTUM  14:30-15:05: first-half-hour return and the day's return agree and price is outside the noise
                   area on that side (Gao et al. JFE 2018: the first half hour predicts the last)
  FIB_GOLDEN_POCKET  pullback into the 0.50-0.618 retracement of an impulse swing that turns back, taken only when
                   the option chain (OI) and futures volume both confirm it (service/fib_pocket.py)

Day type (service/day_type.py) decides which setups may trade at all (confirm_timeframes()):
  PIN / RANGE        only REVERSAL and RANGE-family setups (theta beats trend-following inside the noise area)
  TREND / EXPANSION  TREND-family setups on the day's side, plus REVERSAL; no VWAP band fades

Timeframes (17 Nov 2026): the signal candle is settings.SIGNAL_TIMEFRAME (detect()); the 5- and 15-minute charts
confirm it by SITUATION, not one fixed rule (tf_agreement(), per setup family):
  REVERSAL  the 5-minute must have turned; the 15-minute may still point the other way
  RANGE     neither the 5- nor the 15-minute against it
  TREND     trend day on its side: 15-min agrees, 5-min not against | opening 45 min: 5-min agrees, 15-min not
            against | volatile tape (VIX spiking): both agree | no day context: both agree
Replay, 6 months of real NIFTY / BANKNIFTY / SENSEX 1-minute data, live pipeline (scripts/compare_signal_timeframes.py):
  5-min signal, old 15-min-only rule      294 trades  PF 1.10  +30.4k  DD 68.3k
  5-min signal, situational  (LIVE)        289 trades  PF 1.13  +36.3k  DD 66.7k   better in both halves
  1-min close completes the 5-min pattern  336 trades  PF 1.00   -0.4k  DD 85.8k
  pure 1-minute patterns                   362 trades  PF 0.88  -37.9k  DD 131.9k
So the 1-minute candle times the entry (one_minute_check(), always run) and the setup fires on the 5-minute close.
one_minute_check() checks: 1-min EMA9 side, no fresh 1-min swing against the trade, setup stop not touched, not
chasing, target not already hit.

Futures OI buildup confirms (+1) or contradicts (-1, flagged) each signal; volume spike adds +1.
"""

from typing import Any

from app.modules.autopsy.service import learning_rules
from app.modules.opportunity_finder.service import fib_pocket
from app.modules.opportunity_finder.service.market_analysis import ema, next_level

MIN_SETUP_RR = 1.3  # underlying reward:risk below this is not a setup


def _plan(a: dict[str, Any], side: str, entry: float, stop: float, atr5: float) -> dict[str, Any] | None:
    up = side == "CE"
    risk = (entry - stop) if up else (stop - entry)
    if risk <= 0:
        return None
    lvl = next_level(a, entry, up, max(risk, 0.3 * atr5))
    if lvl:
        target, target_name = lvl[1], lvl[0]
    else:
        target, target_name = (entry + 2 * risk) if up else (entry - 2 * risk), "2R"
    reward = (target - entry) if up else (entry - target)
    rr = reward / risk
    if rr < MIN_SETUP_RR:
        # the next level is too close: fall back to 2R only if nothing blocks the way
        return None
    return {"entry": round(entry, 2), "stop": round(stop, 2), "target": round(target, 2),
            "targetLevel": target_name, "rr": round(rr, 2)}


def _fixed_plan(entry: float, stop: float, target: float, target_name: str, up: bool) -> dict[str, Any] | None:
    """A plan whose target is given (e.g. VWAP for a band fade) instead of the next key level."""
    risk = (entry - stop) if up else (stop - entry)
    reward = (target - entry) if up else (entry - target)
    if risk <= 0 or reward <= 0 or reward / risk < MIN_SETUP_RR:
        return None
    return {"entry": round(entry, 2), "stop": round(stop, 2), "target": round(target, 2),
            "targetLevel": target_name, "rr": round(reward / risk, 2)}


def _signal(name, side, plan, strength, reason) -> dict[str, Any]:
    return {"name": name, "side": side, "strength": strength, "reason": reason, **plan}


SIGNAL_MODES = ("5m", "1m_trigger", "1m")


def signal_mode() -> str:
    from app.core.config.settings import settings  # lazy: keeps this module importable without app config

    m = (getattr(settings, "SIGNAL_TIMEFRAME", "5m") or "5m").strip()
    return m if m in SIGNAL_MODES else "5m"


def detect(a: dict[str, Any], cfg: Any, mode: str | None = None) -> list[dict[str, Any]]:
    """Every setup on the signal timeframe (17 Nov 2026, `mode` / settings.SIGNAL_TIMEFRAME):
      5m          the last COMPLETED 5-minute bar is the signal (the engine until 17 Nov 2026)
      1m_trigger  the 5-minute pattern is read on the 5-minute bars including the one still forming, updated to the
                  last completed 1-minute bar: the signal fires on the 1-MINUTE close that completes the pattern
                  instead of waiting for the 5-minute close. Structure and ATR stay 5-minute (the tested ones)
      1m          the patterns run on the 1-minute candles themselves with the 1-minute ATR
    The 5- and 15-minute charts then confirm it (confirm_timeframes -> tf_agreement)."""
    mode = mode or signal_mode()
    if mode == "1m":
        bars, atr5, fut = a.get("bars1") or [], a.get("atr1") or 0.0, a.get("futBars1") or []
    elif mode == "1m_trigger":
        bars, atr5, fut = a.get("bars5Live") or a.get("bars5") or [], a.get("atr5") or 0.0, a.get("futBars5") or []
    else:
        bars, atr5, fut = a.get("bars5") or [], a.get("atr5") or 0.0, a.get("futBars5") or []
    if len(bars) < 3:
        return []
    lv = a.get("levels") or {}
    if atr5 <= 0:
        return []
    regime = a.get("regime", "MIXED")
    trend = a.get("trend15", "FLAT")
    vol = a.get("volume") or {}
    spike = bool(vol.get("spike"))
    last, prev = bars[-1], bars[-2]
    rng = max(last["h"] - last["l"], 1e-9)
    tick = 0.1 * atr5
    out: list[dict[str, Any]] = []

    # 1. Opening range breakout
    oh, ol = lv.get("orHigh"), lv.get("orLow")
    if oh and ol and regime != "RANGE":
        if last["c"] > oh >= prev["c"]:
            p = _plan(a, "CE", last["c"], min(last["l"], (oh + ol) / 2) - tick, atr5)
            if p:
                out.append(_signal("ORB", "CE", p, 2 + spike, f"5-min close {last['c']:.1f} above opening-range high {oh:.1f}"))
        if last["c"] < ol <= prev["c"]:
            p = _plan(a, "PE", last["c"], max(last["h"], (oh + ol) / 2) + tick, atr5)
            if p:
                out.append(_signal("ORB", "PE", p, 2 + spike, f"5-min close {last['c']:.1f} below opening-range low {ol:.1f}"))

    # 2. VWAP pullback (futures VWAP; touch measured on the futures bar)
    vw = a.get("vwap")
    fb = fut
    if vw and fb and regime in ("TREND", "MIXED"):
        v, f = vw["value"], fb[-1]
        recent = fb[-7:-1]
        if trend == "UP" and f["l"] <= v * 1.0008 and f["c"] > v and f["c"] > f["o"] and sum(b["c"] > v for b in recent) >= 3:
            p = _plan(a, "CE", last["c"], last["l"] - tick, atr5)
            if p:
                out.append(_signal("VWAP_PULLBACK", "CE", p, 3, "15-min uptrend, pullback to futures VWAP bought"))
        if trend == "DOWN" and f["h"] >= v * 0.9992 and f["c"] < v and f["c"] < f["o"] and sum(b["c"] < v for b in recent) >= 3:
            p = _plan(a, "PE", last["c"], last["h"] + tick, atr5)
            if p:
                out.append(_signal("VWAP_PULLBACK", "PE", p, 3, "15-min downtrend, pullback to futures VWAP sold"))

    # 3. Previous-day high / low break and retest
    pdh, pdl = lv.get("pdh"), lv.get("pdl")
    earlier = bars[:-1]
    if pdh and any(b["c"] > pdh for b in earlier) and last["l"] <= pdh + 1.5 * tick and last["c"] > pdh and last["c"] >= last["o"]:
        p = _plan(a, "CE", last["c"], min(last["l"], pdh) - tick, atr5)
        if p:
            out.append(_signal("PDH_PDL_RETEST", "CE", p, 3, f"previous-day high {pdh:.1f} broken, retested and held"))
    if pdl and any(b["c"] < pdl for b in earlier) and last["h"] >= pdl - 1.5 * tick and last["c"] < pdl and last["c"] <= last["o"]:
        p = _plan(a, "PE", last["c"], max(last["h"], pdl) + tick, atr5)
        if p:
            out.append(_signal("PDH_PDL_RETEST", "PE", p, 3, f"previous-day low {pdl:.1f} broken, retested and held"))

    # 4. Narrow-CPR breakout
    tc, bc = lv.get("tc"), lv.get("bc")
    if lv.get("cprNarrow") and tc and bc:
        if last["c"] > tc >= prev["c"]:
            p = _plan(a, "CE", last["c"], last["l"] - tick, atr5)
            if p:
                out.append(_signal("CPR_BREAKOUT", "CE", p, 2 + spike, "narrow CPR (trend-day candidate), close above TC"))
        if last["c"] < bc <= prev["c"]:
            p = _plan(a, "PE", last["c"], last["h"] + tick, atr5)
            if p:
                out.append(_signal("CPR_BREAKOUT", "PE", p, 2 + spike, "narrow CPR (trend-day candidate), close below BC"))

    # 5. OI wall rejection
    oi = a.get("oi") or {}
    res, sup = oi.get("resistance"), oi.get("support")
    if regime in ("RANGE", "MIXED"):
        upper_wick = last["h"] - max(last["o"], last["c"])
        lower_wick = min(last["o"], last["c"]) - last["l"]
        if res and last["h"] >= res - tick and last["c"] < res and upper_wick >= 0.5 * rng and last["c"] < last["o"]:
            p = _plan(a, "PE", last["c"], last["h"] + tick, atr5)
            if p:
                out.append(_signal("OI_WALL_REJECT", "PE", p, 2, f"rejected at the highest call-OI strike {res:.0f}"))
        if sup and last["l"] <= sup + tick and last["c"] > sup and lower_wick >= 0.5 * rng and last["c"] > last["o"]:
            p = _plan(a, "CE", last["c"], last["l"] - tick, atr5)
            if p:
                out.append(_signal("OI_WALL_REJECT", "CE", p, 2, f"bounced at the highest put-OI strike {sup:.0f}"))

    # 6. Momentum flag: impulse -> tight pause -> break of the pause
    if regime != "RANGE":
        flag = _momentum_flag(bars, atr5)
        if flag:
            side, imp, base_hi, base_lo = flag
            if side == "CE":
                p = _plan(a, "CE", last["c"], base_lo - tick, atr5)
                reason = f"impulse +{imp:.1f} pts, tight pause, broke pause high {base_hi:.1f}"
            else:
                p = _plan(a, "PE", last["c"], base_hi + tick, atr5)
                reason = f"impulse -{imp:.1f} pts, tight pause, broke pause low {base_lo:.1f}"
            if p:
                out.append(_signal("MOMENTUM_FLAG", side, p, 3 + spike, reason))

    out += _extra_setups(a, bars, lv, atr5, regime, trend, spike, tick)
    out += fib_pocket.detect(a, bars, atr5, tick)  # 18. Fib golden pocket (OI + volume confirmed)

    if mode != "5m":
        for x in out:
            x["signalTf"] = mode
            x["reason"] = (x["reason"].replace("5-min", "1-min") if mode == "1m"
                           else f"{x['reason']} (signal on the 1-min close)")
    # confirmation by futures OI buildup and trend
    bu = (a.get("buildup") or {}).get("state")
    for s in out:
        ce = s["side"] == "CE"
        confirms = bu in (("LONG_BUILDUP", "SHORT_COVERING") if ce else ("SHORT_BUILDUP", "LONG_UNWINDING"))
        contradicts = bu in (("SHORT_BUILDUP", "LONG_UNWINDING") if ce else ("LONG_BUILDUP", "SHORT_COVERING"))
        s["withTrend"] = trend == ("UP" if ce else "DOWN")
        s["strength"] += (1 if confirms else 0) - (1 if contradicts else 0) + (1 if s["withTrend"] else 0)
        s["strength"] = max(1, min(5, s["strength"]))
        s["conflict"] = f"futures show {bu}" if contradicts else None
    out.sort(key=lambda s: -s["strength"])
    return out


def _momentum_flag(bars: list[dict[str, Any]], atr5: float) -> tuple[str, float, float, float] | None:
    """Impulse of 1-3 bars moving >= 2 ATR, then 2-6 bars pausing inside the impulse's outer half
    with a range <= 60% of the impulse, then the LAST bar closes beyond the pause (fresh break)."""
    last = bars[-1]
    for base_len in range(2, 7):
        base = bars[-1 - base_len:-1]
        if len(base) < base_len:
            break
        for imp_len in (1, 2, 3):
            imp = bars[-1 - base_len - imp_len:-1 - base_len]
            if len(imp) < imp_len:
                continue
            start, end = imp[0]["o"], imp[-1]["c"]
            move = end - start
            if abs(move) < 2 * atr5:
                continue
            hi, lo = max(b["h"] for b in base), min(b["l"] for b in base)
            if hi - lo > 0.6 * abs(move):
                continue
            mid = start + move / 2
            if move > 0 and lo > mid and last["c"] > hi and all(b["c"] <= hi for b in base):
                return "CE", move, hi, lo
            if move < 0 and hi < mid and last["c"] < lo and all(b["c"] >= lo for b in base):
                return "PE", -move, hi, lo
    return None


# ───────────────────────── additional trader setups ─────────────────────────
def _extra_setups(a: dict[str, Any], bars: list[dict[str, Any]], lv: dict[str, Any], atr5: float, regime: str,
                  trend: str, spike: bool, tick: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    last, prev = bars[-1], bars[-2]

    def add(name: str, side: str, stop: float, strength: int, reason: str) -> None:
        p = _plan(a, side, last["c"], stop, atr5)
        if p:
            out.append(_signal(name, side, p, strength, reason))

    green, red = last["c"] > last["o"], last["c"] < last["o"]

    # 7. EMA 9/21 cross with retest (5-minute)
    es = a.get("emaSeries5") or {}
    e9, e21 = es.get("e9") or [], es.get("e21") or []
    if regime in ("TREND", "MIXED") and len(e9) >= 6 and len(e9) == len(e21):
        n = len(e9)
        for look in range(2, min(n - 1, 12)):  # cross happened `look` bars ago
            i = n - look
            up_cross = e9[i - 1] <= e21[i - 1] and e9[i] > e21[i]
            dn_cross = e9[i - 1] >= e21[i - 1] and e9[i] < e21[i]
            after = bars[len(bars) - look:-1] if look > 1 else []
            if up_cross and e9[-1] > e21[-1] and green and last["c"] > e9[-1] and after \
                    and min(b["l"] for b in after + [last]) <= e9[-1] + tick:
                add("EMA_CROSS_RETEST", "CE", min(last["l"], e21[-1]) - tick, 3,
                    f"5-min EMA9 crossed above EMA21 {look} bars ago, pullback held the EMAs")
                break
            if dn_cross and e9[-1] < e21[-1] and red and last["c"] < e9[-1] and after \
                    and max(b["h"] for b in after + [last]) >= e9[-1] - tick:
                add("EMA_CROSS_RETEST", "PE", max(last["h"], e21[-1]) + tick, 3,
                    f"5-min EMA9 crossed below EMA21 {look} bars ago, pullback rejected at the EMAs")
                break

    # 8. Supertrend flip / retest (5-minute)
    st = a.get("supertrend5")
    if st:
        up, since, line = st["dir"] == "UP", st["barsSinceFlip"], st["line"]
        if since == 0 and regime != "RANGE":
            add("SUPERTREND_FLIP", "CE" if up else "PE", line + (-tick if up else tick), 2 + spike,
                f"5-min Supertrend flipped {'up' if up else 'down'} (line {line:.1f})")
        elif 1 <= since <= 12 and regime in ("TREND", "MIXED"):
            if up and last["l"] <= line + 0.5 * atr5 and last["c"] > line and green:
                add("SUPERTREND_RETEST", "CE", line - tick, 3, f"retest of the 5-min Supertrend support {line:.1f} held")
            if not up and last["h"] >= line - 0.5 * atr5 and last["c"] < line and red:
                add("SUPERTREND_RETEST", "PE", line + tick, 3, f"retest of the 5-min Supertrend resistance {line:.1f} rejected")

    # 9. Inside bar: bars[-2] sits inside bars[-3] (the mother bar); the last bar closes beyond the mother
    if len(bars) >= 3:
        mother = bars[-3]
        inside = prev["h"] <= mother["h"] and prev["l"] >= mother["l"] and (mother["h"] - mother["l"]) >= 0.8 * atr5
        if inside and last["c"] > mother["h"]:
            add("INSIDE_BAR", "CE", min(last["l"], prev["l"]) - tick, 2 + spike, f"closed above the mother bar high {mother['h']:.1f}")
        if inside and last["c"] < mother["l"]:
            add("INSIDE_BAR", "PE", max(last["h"], prev["h"]) + tick, 2 + spike, f"closed below the mother bar low {mother['l']:.1f}")

    # 10. Range breakout: 8+ bars squeezed into <= 3 ATR, then a close beyond the box
    if len(bars) >= 9:
        box = bars[-9:-1]
        hi, lo = max(b["h"] for b in box), min(b["l"] for b in box)
        if hi - lo <= 3 * atr5:
            if last["c"] > hi:
                add("RANGE_BREAKOUT", "CE", max(lo, last["c"] - 1.5 * atr5) - tick, 2 + spike, f"closed above the {len(box)}-bar range high {hi:.1f}")
            if last["c"] < lo:
                add("RANGE_BREAKOUT", "PE", min(hi, last["c"] + 1.5 * atr5) + tick, 2 + spike, f"closed below the {len(box)}-bar range low {lo:.1f}")

    # 11. Gap-and-Go: 0.5-2% gap that never fills, close holds above open AND futures VWAP (reverse for a
    # gap down), at least 75% of this session's 5-min futures closes agree with the gap side, price is not
    # chasing (within 0.4% of VWAP), only between ~09:30 and ~10:45. Invalidation: whichever of VWAP/open is
    # nearer to price right now, minus about one 5-minute move (atr5).
    gap, pdc, day_o = lv.get("gapPct"), lv.get("pdc"), lv.get("dayOpen")
    since_open = (a.get("session") or {}).get("minutesSinceOpen", 0)
    vw = a.get("vwap")
    vw_series = a.get("vwapSeries5") or []
    fb = a.get("futBars5") or []
    if gap is not None and pdc and day_o and vw and 0.5 <= abs(gap) <= 2.0 and 15 <= since_open <= 90:
        gap_up = gap > 0
        gap_still_open = lv.get("dayLow", 0) > pdc if gap_up else lv.get("dayHigh", float("inf")) < pdc
        holds = (last["c"] > day_o and vw["above"]) if gap_up else (last["c"] < day_o and not vw["above"])
        not_chasing = abs(vw["distPct"]) <= 0.4
        on_side = sum(
            1 for i, b in enumerate(fb)
            if i < len(vw_series) and vw_series[i] is not None
            and ((b["c"] > vw_series[i]) if gap_up else (b["c"] < vw_series[i]))
        )
        counted = sum(1 for v in vw_series if v is not None)
        strong = counted > 0 and on_side / counted >= 0.75
        if gap_still_open and holds and not_chasing and strong:
            nearer = day_o if abs(last["c"] - day_o) <= abs(last["c"] - vw["value"]) else vw["value"]
            direction = "gap-up" if gap_up else "gap-down"
            side_word = "above" if gap_up else "below"
            reason = (f"{direction} {gap:+.2f}% holding {side_word} open and VWAP, {on_side}/{counted} "
                      f"5-min bars on the gap side, {abs(vw['distPct']):.2f}% off VWAP")
            stop = (nearer - atr5) if gap_up else (nearer + atr5)
            add("GAP_GO", "CE" if gap_up else "PE", stop, 3, reason)

    # 12. PCR / option-OI shift: DEMOTED from an independent trigger (10 Nov 2026 research review -- Jena,
    # Tiwari & Mitra, Economies 2019: NSE volume-PCR has no predictive power on returns, and NIFTY returns
    # Granger-cause PCR, not the other way; OI-PCR only predicts at a 12-day-plus horizon, useless intraday).
    # `a["oiShift"]` is still computed and left in the analysis dict for `menu_builder.pcr_adjustment()` to use
    # as a small confidence nudge on whatever OTHER setup fired on that side -- never as its own trade.

    # 13. Short-covering spike (CE) / long-unwinding spike (PE): price and OI move opposite, on a volume spike
    bu = a.get("buildup") or {}
    if spike:
        if bu.get("state") == "SHORT_COVERING" and bu.get("oiChgPct", 0) <= -0.15 and green:
            add("SHORT_COVERING_SPIKE", "CE", last["l"] - tick, 3, f"futures up {bu['priceChgPct']:+.2f}% with OI {bu['oiChgPct']:+.2f}% on a volume spike")
        if bu.get("state") == "LONG_UNWINDING" and bu.get("oiChgPct", 0) <= -0.15 and red:
            add("SHORT_COVERING_SPIKE", "PE", last["h"] + tick, 3, f"futures down {bu['priceChgPct']:+.2f}% with OI {bu['oiChgPct']:+.2f}% on a volume spike (long unwinding)")

    # 14. Failed break -> reclaim (and the opening-range fade): a level swept by >= 0.1 ATR, then a 5-min close back
    #     through it. Fresh only: this bar is the reclaim (the previous close was still on the broken side, or this
    #     bar itself swept and closed back).
    oi_ctx = a.get("oi") or {}
    vwa = a.get("vwap") or {}
    window = bars[-6:]
    lows = [("OR low", lv.get("orLow")), ("previous-day low", lv.get("pdl")), ("S1", lv.get("s1")),
            ("CPR BC", lv.get("bc")), ("pivot", lv.get("pivot")), ("put-OI strike", oi_ctx.get("support"))]
    highs = [("OR high", lv.get("orHigh")), ("previous-day high", lv.get("pdh")), ("R1", lv.get("r1")),
             ("CPR TC", lv.get("tc")), ("pivot", lv.get("pivot")), ("call-OI strike", oi_ctx.get("resistance"))]
    sweep_lo, sweep_hi = min(b["l"] for b in window), max(b["h"] for b in window)
    # round numbers: stop orders cluster just beyond them (Osler 2005). The round level is the one that was swept.
    step = (lv.get("roundAbove") or 0) - (lv.get("roundBelow") or 0)
    if step > 0:
        lows.append(("round number", -(-sweep_lo // step) * step))
        highs.append(("round number", (sweep_hi // step) * step))
    lo_i = len(bars) - len(window) + min(range(len(window)), key=lambda i: window[i]["l"])
    hi_i = len(bars) - len(window) + max(range(len(window)), key=lambda i: window[i]["h"])
    before_lo, before_hi = bars[max(0, lo_i - 12):lo_i], bars[max(0, hi_i - 12):hi_i]
    for name, L in lows:
        if not L or not green:
            continue
        # a breakDOWN needs the level to have held first: some close above it before the sweep bar
        swept = sweep_lo <= L - tick and any(b["c"] > L for b in before_lo)
        fresh = prev["c"] <= L or (last["l"] <= L - tick)
        if swept and fresh and last["c"] > L + 0.5 * tick:
            boost = 1 if vwa and vwa.get("above") else 0
            add("FAILED_BREAK_RECLAIM", "CE", sweep_lo - tick, 3 + boost + spike,
                f"broke the {name} {L:.1f} (low {sweep_lo:.1f}) and closed back above it -- failed breakdown")
            break
    for name, L in highs:
        if not L or not red:
            continue
        swept = sweep_hi >= L + tick and any(b["c"] < L for b in before_hi)
        fresh = prev["c"] >= L or (last["h"] >= L + tick)
        if swept and fresh and last["c"] < L - 0.5 * tick:
            boost = 1 if vwa and vwa.get("above") is False else 0
            add("FAILED_BREAK_RECLAIM", "PE", sweep_hi + tick, 3 + boost + spike,
                f"broke the {name} {L:.1f} (high {sweep_hi:.1f}) and closed back below it -- failed breakout")
            break

    # 15. VWAP band reversion: only on a balanced day (flat VWAP), back inside the +/- 2 SD band, target = VWAP.
    sd, slope = vwa.get("sd") or 0.0, vwa.get("slopePct")
    fb5 = a.get("futBars5") or []
    if vwa and sd > 0 and slope is not None and abs(slope) <= 0.05 and regime in ("RANGE", "MIXED") and len(fb5) >= 2:
        v, fl, fp = vwa["value"], fb5[-1], fb5[-2]
        upper, lower = v + 2 * sd, v - 2 * sd
        to_vwap = abs(fl["c"] - v)  # the futures distance back to VWAP, applied to the spot entry
        if fp["h"] >= upper and fl["c"] < upper and red and fl["c"] > v:
            stop = max(last["h"], prev["h"]) + tick
            plan = _fixed_plan(last["c"], stop, last["c"] - to_vwap, "VWAP", up=False)
            if plan:
                out.append(_signal("VWAP_BAND_REVERT", "PE", plan, 2,
                                   f"stretched above VWAP +2 SD ({upper:.1f}) on a flat-VWAP day, closed back inside"))
        if fp["l"] <= lower and fl["c"] > lower and green and fl["c"] < v:
            stop = min(last["l"], prev["l"]) - tick
            plan = _fixed_plan(last["c"], stop, last["c"] + to_vwap, "VWAP", up=True)
            if plan:
                out.append(_signal("VWAP_BAND_REVERT", "CE", plan, 2,
                                   f"stretched below VWAP -2 SD ({lower:.1f}) on a flat-VWAP day, closed back inside"))

    # 16. Noise-area breakout: the first 5-min close outside the band (the previous close was inside).
    noise = a.get("noise") or {}
    # Zarattini et al. entry: outside the noise band AND on the right side of VWAP (no VWAP read = no veto)
    vw_side = (a.get("vwap") or {}).get("above")
    vw_ok_ce, vw_ok_pe = vw_side is not False, vw_side is not True
    if noise.get("prevState") == "INSIDE" and noise.get("state") in ("ABOVE", "BELOW"):
        if noise["state"] == "ABOVE" and green and vw_ok_ce:
            add("NOISE_BREAKOUT", "CE", min(last["l"], noise["upper"]) - tick, 3 + spike,
                f"5-min close {last['c']:.1f} above the noise area {noise['upper']:.1f} (move is no longer noise)")
        if noise["state"] == "BELOW" and red and vw_ok_pe:
            add("NOISE_BREAKOUT", "PE", max(last["h"], noise["lower"]) + tick, 3 + spike,
                f"5-min close {last['c']:.1f} below the noise area {noise['lower']:.1f} (move is no longer noise)")

    # 17. Late-day momentum: first half hour and the whole day point the same way, price outside the noise area.
    sess = a.get("session") or {}
    fh, pdc2 = a.get("firstHalfHourRetPct"), lv.get("pdc")
    from app.core.config.settings import settings as _st
    from app.modules.opportunity_finder.service.institutional_filters import enabled as _inst_on

    lo_m, hi_m = LATE_MOMO_LAST_WINDOW if "LATE_WINDOW_LAST" in _inst_on(_st.INSTITUTIONAL_FILTERS) else LATE_MOMO_MIN_TO_CLOSE
    if fh is not None and pdc2 and lo_m <= sess.get("minutesToClose", 0) <= hi_m:
        day_ret = (last["c"] - pdc2) / pdc2 * 100
        recent = bars[-3:]
        if fh > 0 and day_ret > 0 and noise.get("state") == "ABOVE" and green:
            add("LATE_DAY_MOMENTUM", "CE", min(b["l"] for b in recent) - tick, 3,
                f"first half hour {fh:+.2f}% and day {day_ret:+.2f}% both up, above the noise area into the close")
        if fh < 0 and day_ret < 0 and noise.get("state") == "BELOW" and red:
            add("LATE_DAY_MOMENTUM", "PE", max(b["h"] for b in recent) + tick, 3,
                f"first half hour {fh:+.2f}% and day {day_ret:+.2f}% both down, below the noise area into the close")

    # 18. Rising/Converging Wedge & Triangle Breakout / Breakdown + RSI(14) + OI/Max Pain alignment
    if len(bars) >= 12:
        win = bars[-13:-1]
        mid = len(win) // 2
        h1, h2 = max(b["h"] for b in win[:mid]), max(b["h"] for b in win[mid:])
        l1, l2 = min(b["l"] for b in win[:mid]), min(b["l"] for b in win[mid:])
        span1, span2 = h1 - l1, h2 - l2
        rsi_val = (a.get("rsi") or {}).get("14") or (a.get("indicators") or {}).get("rsi14")
        converging = span1 > 0 and span2 > 0 and span2 < span1 * 0.90 and l2 >= l1
        if converging:
            if last["c"] > h2 and green and (rsi_val is None or float(rsi_val) >= 54):
                add(
                    "WEDGE_BREAKOUT",
                    "CE",
                    min(last["l"], l2) - tick,
                    4 + spike,
                    f"Wedge breakout above {h2:.1f} (higher lows {l1:.1f}->{l2:.1f})"
                    + (f" with RSI14={float(rsi_val):.1f}" if rsi_val is not None else ""),
                )
            elif last["c"] < l2 and red and (rsi_val is None or float(rsi_val) <= 46):
                add(
                    "WEDGE_BREAKDOWN",
                    "PE",
                    max(last["h"], h2) + tick,
                    4 + spike,
                    f"Rising wedge breakdown below {l2:.1f} (from {l1:.1f}->{l2:.1f})"
                    + (f" with RSI14={float(rsi_val):.1f}" if rsi_val is not None else ""),
                )

    # 19. Fast 1m/5m Scalper Impulse: tight stop under impulse bar, quick scalp momentum with volume >= 1.25x
    if len(bars) >= 4:
        prev_b = bars[-2]
        body_sz = abs(last["c"] - last["o"])
        bar_rng = max(tick, last["h"] - last["l"])
        vol_ok = spike >= 1 or (float(last.get("v") or 0) >= 1.25 * max(1.0, float(prev_b.get("v") or 0)))
        if vol_ok and body_sz >= bar_rng * 0.55 and atr5 > 0 and bar_rng >= 0.45 * atr5:
            if green and last["c"] > prev_b["h"] and vw_ok_ce:
                add("SCALP_IMPULSE", "CE", last["l"] - tick, 4 + spike,
                    f"Scalper impulse bar above {prev_b['h']:.1f} with tight SL {last['l'] - tick:.1f}")
            elif red and last["c"] < prev_b["l"] and vw_ok_pe:
                add("SCALP_IMPULSE", "PE", last["h"] + tick, 4 + spike,
                    f"Scalper impulse breakdown below {prev_b['l']:.1f} with tight SL {last['h'] + tick:.1f}")

    # 20. Post-1:45 PM Expiry Gamma Blast (NIFTY Tuesday / SENSEX Thursday)
    # Trigger: Time >= 13:45 IST, tight afternoon base breakout crossing round-number/heavy OI strike with volume spike
    last_t = str(last.get("t") or "")[11:16]
    is_expiry_time = "13:45" <= last_t <= "15:15"
    if is_expiry_time and len(bars) >= 6:
        prior_5 = bars[-6:-1]
        hi_5 = max(b["h"] for b in prior_5)
        lo_5 = min(b["l"] for b in prior_5)
        consolidation_tight = (hi_5 - lo_5) <= 1.8 * atr5
        if consolidation_tight:
            vw_val = vw.get("value") if isinstance(vw, dict) else None
            vw_above = (last["c"] > vw_val) if vw_val is not None else False
            vw_below = (last["c"] < vw_val) if vw_val is not None else False
            if green and last["c"] > hi_5 and (spike >= 1 or vw_above):
                add(
                    "GAMMA_BLAST",
                    "CE",
                    lo_5 - tick,
                    5 + spike,
                    f"Post-1:45 PM Expiry Gamma Blast breakout above {hi_5:.1f} (tight base {hi_5 - lo_5:.1f} pts)",
                )
            elif red and last["c"] < lo_5 and (spike >= 1 or vw_below):
                add(
                    "GAMMA_BLAST",
                    "PE",
                    hi_5 + tick,
                    5 + spike,
                    f"Post-1:45 PM Expiry Gamma Blast breakdown below {lo_5:.1f} (tight base {hi_5 - lo_5:.1f} pts)",
                )

    # 21. Liquidity Sweep & Trapped Stop-Hunt Reversal
    # Trigger: Sweep of PDH or PDL by >= 0.1 ATR that immediately closes back inside with VWAP reclaim
    pdh = lv.get("pdh")
    pdl = lv.get("pdl")
    if pdl and last["l"] <= pdl - 0.1 * atr5 and last["c"] > pdl and green:
        sl = min(last["l"], min((b["l"] for b in bars[-3:]), default=last["l"])) - tick
        add(
            "LIQUIDITY_SWEEP",
            "CE",
            sl,
            5 + spike,
            f"Liquidity sweep below PDL {pdl:.1f} reclaimed with bullish reversal candle",
        )
    elif pdh and last["h"] >= pdh + 0.1 * atr5 and last["c"] < pdh and red:
        sl = max(last["h"], max((b["h"] for b in bars[-3:]), default=last["h"])) + tick
        add(
            "LIQUIDITY_SWEEP",
            "PE",
            sl,
            5 + spike,
            f"Liquidity sweep above PDH {pdh:.1f} rejected with bearish reversal candle",
        )

    return out


# ───────────────────────── multi-timeframe confirmation ─────────────────────────
RANGE_SETUPS = {"PDH_PDL_RETEST", "OI_WALL_REJECT", "VWAP_BAND_REVERT"}  # PCR_SHIFT demoted 10 Nov 2026
REVERSAL_SETUPS = {"FAILED_BREAK_RECLAIM"}
LATE_MOMO_MIN_TO_CLOSE = (35, 70)  # 14:30-15:05 on a 15:40 close
LATE_MOMO_LAST_WINDOW = (12, 50)  # institutional filter LATE_WINDOW_LAST: 14:50-15:28 on a 15:40 close


def day_type_block(a: dict[str, Any], s: dict[str, Any]) -> str | None:
    """Why today's day type does not allow this setup, or None. No day type (no noise area yet) = no veto.

    `dayBias` (day_type.apply_bias(), 10 Nov 2026 post-mortem) is the STICKY call for the session, separate from
    the instantaneous `dayType`: once the day has confirmed EXPANSION on a side, every family -- REVERSAL
    (FAILED_BREAK_RECLAIM) included -- is blocked from trading the other side, even during a pullback that reads
    back as RANGE/PIN a few minutes later. A plain TREND bias (no fuel yet) still allows a REVERSAL bet against
    it, since an unconfirmed trend is exactly the setup "a reclaimed level is how a V-day turns" is for."""
    dt = a.get("dayType") or {}
    kind = dt.get("type")
    bias = a.get("dayBias") or {}
    if bias.get("type") == "EXPANSION" and bias.get("side") and s["side"] != bias["side"]:
        return f"EXPANSION bias ({bias['side']}) still in force for the session: no trades against it"
    fam = family(s["name"])
    gap_block = unfilled_gap_block(a.get("levels") or {}, fam)
    if gap_block:
        return gap_block
    if not kind:
        return None
    if kind in ("PIN", "RANGE"):
        if fam == "TREND":
            return f"{kind} day (price inside the noise area): trend/breakout setups are not traded"
        return None
    if s["name"] == "VWAP_BAND_REVERT":
        return f"{kind} day: no VWAP fades against an expanding move"
    if fam == "TREND" and dt.get("side") and s["side"] != dt["side"]:
        return f"{kind} day is on the {dt['side']} side"
    return None


# 11 Nov 2026 research review (gap 4): gap size is a regime signal. 148 NIFTY expiries (Quintal Mind, 2026):
# gaps < 0.1% filled 89% of the time, gaps > 0.5% only 25% -- "the big gaps are the trend days". 11 Nov 2026 gapped
# +1.1% and never filled; the classifier read the pullback as RANGE and FAILED_BREAK_RECLAIM lost on 4 of 5 fires.
# Rule: while a gap of BIG_GAP_PCT or more is still unfilled, no mean-reversion family (REVERSAL / RANGE) trades.
BIG_GAP_PCT = 0.5


def unfilled_gap_block(lv: dict[str, Any], fam: str) -> str | None:
    gap, pdc = lv.get("gapPct"), lv.get("pdc")
    hi, lo = lv.get("dayHigh"), lv.get("dayLow")
    if fam == "TREND" or gap is None or not pdc or hi is None or lo is None or abs(gap) < BIG_GAP_PCT:
        return None
    filled = lo <= pdc if gap > 0 else hi >= pdc
    if filled:
        return None
    return (f"unfilled {gap:+.2f}% gap (>= {BIG_GAP_PCT}%): trend-day odds, no {fam.lower()} setups "
            f"until price trades back to the previous close {pdc:.1f}")


# ───────────────────────── setup policy (11 Nov 2026 institutional-strategy review) ─────────────────────────
# Institutions earn from short-dated premium (VRP) and from trading WITH hedging flows (intraday momentum), not from
# chart patterns. Vendor backtests of the retail versions on NIFTY (Oct 2025-Sep 2026) were mostly negative even before
# costs (ORB option buying -70.5k, inside bar -2.68L, PDH/PDL breakout -24.6k, VWAP band fade -91.4k, max-OI strike
# -54.2k), and FAILED_BREAK_RECLAIM / PDH_PDL_RETEST were the most-stopped setups in our own replays.
#   CORE                 the directional engine: noise-area breakout + late-day momentum (Baltussen et al. JFE 2021,
#                        Zarattini et al. 2024, Gao et al. JFE 2018)
#   MERGED               only as an extra entry INSIDE an active noise breakout on the same side (day type / sticky
#                        bias TREND or EXPANSION on that side); never on its own
#   SHORT_PREMIUM_ONLY   mean-reversion reads: not bought as options any more; they only inform where a defined-risk
#                        short-premium structure is centred (iron_fly.py), and only in a positive-gamma regime
#   CONFIRMED            a pattern setup that may trade only with its own OI + volume confirmations (fib_pocket.py)
#   DROPPED              no entry at all (kept detectable for research replays / the funnel report)
SETUP_POLICY: dict[str, str] = {
    "NOISE_BREAKOUT": "CORE",
    # 18 Nov 2026 live-pipeline replay, 4 May - 11 Nov (132 days, NIFTY/BANKNIFTY/SENSEX, both managers, HIGH risk):
    # RANGE_BREAKOUT 67 trades -23.4k (H1 -22.2k / H2 -1.2k), LATE_DAY_MOMENTUM 18 trades -11.0k (H1 -9.1k / H2 -1.9k):
    # negative in BOTH halves -> dropped. Re-run without them: 421 -> 357 trades, net +79.0k -> +113.6k, PF 1.17 -> 1.30,
    # H1 -20.9k -> +6.4k, max drawdown 81.0k -> 69.6k (Black-Scholes premiums, per lot).
    "LATE_DAY_MOMENTUM": "DROPPED",
    "RANGE_BREAKOUT": "DROPPED", "VWAP_PULLBACK": "MERGED", "GAP_GO": "MERGED",
    "FAILED_BREAK_RECLAIM": "SHORT_PREMIUM_ONLY", "VWAP_BAND_REVERT": "SHORT_PREMIUM_ONLY",
    "OI_WALL_REJECT": "SHORT_PREMIUM_ONLY",
    # 12 Nov 2026 price-action study: INSIDE_BAR alone 14 trades PF 14.7. 17 Nov 2026 live-pipeline replay (May-Nov,
    # after situational 5m/15m confirmation): 35 trades, 17% wins, -23.1k H1 / -16.0k H2 -> dropped.
    # Scalp (fixed 1R / 1.5R) exits lost after costs on every setup tested.
    "INSIDE_BAR": "DROPPED",
    "SCALP_IMPULSE": "CORE",
    "WEDGE_BREAKOUT": "CORE",
    "WEDGE_BREAKDOWN": "CORE",
    "GAMMA_BLAST": "CORE",
    "LIQUIDITY_SWEEP": "CORE",
    "FII_OPEN_DRIVE": "CORE",  # opening CE on prior-day FII futures buying (fii_open.py); off unless FII_OPEN_CODES
    # 16 Nov 2026: the Fib Golden-Pocket Trader's only setup. CONFIRMED = trades only when fib_pocket.py found BOTH
    # its OI and its volume confirmation (a signal carrying `confirmBlock` is rejected). Not backtested yet.
    "FIB_GOLDEN_POCKET": "CONFIRMED",
    # 17 Nov 2026: the Commodity Desk's setups (modules/commodity_desk). CONFIRMED = only after the desk's own risk
    # gate and head trader took them; they never reach a session not run by the Commodity Desk.
    "DESK_TREND_PULLBACK": "CONFIRMED", "DESK_RANGE_BREAK": "CONFIRMED", "DESK_FIB_POCKET": "CONFIRMED",
    "ORB": "DROPPED", "EMA_CROSS_RETEST": "DROPPED", "PDH_PDL_RETEST": "DROPPED",
    "MOMENTUM_FLAG": "DROPPED", "SHORT_COVERING_SPIKE": "DROPPED", "SUPERTREND_FLIP": "DROPPED",
    "SUPERTREND_RETEST": "DROPPED", "CPR_BREAKOUT": "DROPPED",
}


def policy_block(a: dict[str, Any], s: dict[str, Any]) -> str | None:
    """Why the setup policy does not allow this signal as an OPTION BUY, or None."""
    pol = SETUP_POLICY.get(s["name"], "DROPPED")  # unknown / new setups must be classified before they trade
    # what finished trades taught (modules/autopsy): a paused setup or an applied guard. Live engine only: the
    # analysis carries "learning" only when the live graph attached it, so backtests are never affected.
    learned = learning_rules.engine_block(a.get("learning"), s["name"], (a.get("session") or {}).get("minutesToClose"))
    if learned:
        return learned
    g = a.get("gamma") or {}
    if g.get("enabled") and pol in ("CORE", "MERGED", "CONFIRMED"):
        r = g.get("route") or {}
        if s["side"] == "PE" and r.get("momentumShort") is False:
            return f"dealer gamma {g.get('regime')}: momentum shorts blocked (mean-reverting tape)"
        if s["side"] == "CE" and r.get("momentumLong") is False:
            return f"dealer gamma {g.get('regime')}: momentum longs blocked"
    from app.core.config.settings import settings  # lazy: keeps this module importable without app config
    from app.modules.opportunity_finder.service import institutional_filters as inst

    extra = inst.block(a, s, a.get("code") or "", inst.enabled(settings.INSTITUTIONAL_FILTERS))
    if extra:
        return extra
    if pol == "CORE":
        return None
    if pol == "CONFIRMED":
        return s.get("confirmBlock")
    if pol == "DROPPED":
        return f"{s['name']} dropped (no evidence of edge after costs)"
    if pol == "SHORT_PREMIUM_ONLY":
        return f"{s['name']} is a mean-reversion read: short-premium placement only, never an option buy"
    dt, bias = a.get("dayType") or {}, a.get("dayBias") or {}
    aligned = any(x.get("type") in ("TREND", "EXPANSION") and x.get("side") == s["side"] for x in (dt, bias))
    return None if aligned else f"{s['name']} only inside an active {s['side']} noise breakout"


def family(name: str) -> str:
    return "REVERSAL" if name in REVERSAL_SETUPS else "RANGE" if name in RANGE_SETUPS else "TREND"

MIN_1M_BARS = 5  # completed 1-minute bars needed before any entry is allowed
EMA_1M = 9
MAX_CHASE_ATR = 0.5  # 1-min price may run at most 0.5 x ATR5 past the setup entry before the trade is "chased"
STOP_LOOKBACK_1M = 5  # the setup stop must not have been touched on any of the last 5 one-minute bars


def one_minute_check(b1: list[dict[str, Any]], s: dict[str, Any], atr5: float) -> tuple[str | None, dict[str, Any]]:
    """Entry-timing gate on the 1-minute chart. Returns (reject_reason | None, info).
    CE (PE is the mirror):
      1. at least MIN_1M_BARS completed 1-minute bars
      2. (dropped) "last 1-min bar green and above the prior close" -- one bar re-read every 20 s flickered and
         missed entries; the EMA9 side + no-fresh-low checks below carry the same intent
      3. 1-min trend: last close above the 1-min EMA9
      4. structure: the entry bar did not make a fresh low below the previous 3 one-minute lows
      5. invalidation: no 1-min low in the last STOP_LOOKBACK_1M bars at/below the setup stop
      6. not chasing: last close no more than MAX_CHASE_ATR x ATR5 above the setup entry
      7. room left: last close still below the setup target
    info carries entry1m (last 1-min close), trigger1m (break of the entry bar high/low) and ema1m."""
    ce = s["side"] == "CE"
    if len(b1) < MIN_1M_BARS:
        return f"only {len(b1)} completed 1-min bars, need {MIN_1M_BARS}", {}
    l1 = b1[-1]
    closes = [b["c"] for b in b1[-30:]]
    e9 = ema(closes, EMA_1M)[-1] if len(closes) >= 2 else closes[-1]
    buf = 0.05 * atr5 if atr5 > 0 else 0.0
    info = {"entry1m": round(l1["c"], 2), "ema1m": round(e9, 2),
            "trigger1m": round(l1["h"] + buf if ce else l1["l"] - buf, 2)}

    if (l1["c"] <= e9) if ce else (l1["c"] >= e9):
        return f"1-min close {l1['c']:.1f} is {'below' if ce else 'above'} 1-min EMA{EMA_1M} {e9:.1f}", info
    prior = b1[-4:-1]
    if ce and l1["l"] < min(b["l"] for b in prior):
        return "1-min entry bar made a fresh lower low", info
    if not ce and l1["h"] > max(b["h"] for b in prior):
        return "1-min entry bar made a fresh higher high", info
    stop, entry, target = s.get("stop"), s.get("entry"), s.get("target")
    recent = b1[-STOP_LOOKBACK_1M:]
    if stop is not None and (any(b["l"] <= stop for b in recent) if ce else any(b["h"] >= stop for b in recent)):
        return f"1-min chart already touched the setup stop {stop:.1f}", info
    if entry is not None and atr5 > 0:
        run = (l1["c"] - entry) if ce else (entry - l1["c"])
        if run > MAX_CHASE_ATR * atr5:
            return f"1-min price ran {run:.1f} pts past the setup entry (chasing, max {MAX_CHASE_ATR * atr5:.1f})", info
    if target is not None and ((l1["c"] >= target) if ce else (l1["c"] <= target)):
        return f"1-min price already at the setup target {target:.1f}", info
    return None, info


OPENING_MIN = 45  # first 45 minutes: few real 15-minute bars of today yet


def tf_agreement(a: dict[str, Any], side: str, fam: str) -> tuple[str | None, str]:
    """How much the 5- and 15-minute charts must agree with a signal, judged from the situation like a desk trader
    (17 Nov 2026: "based on the situation, not a hard-coded flow"). Returns (reject_reason | None, why_it_passed).

      REVERSAL family     the 5-minute must have TURNED to the signal's side; the 15-minute may still point the
                          other way (a reversal is early on the bigger chart by definition)
      RANGE family        15-minute flat or with the signal, 5-minute not against it
      TREND family:
        volatile tape     (India VIX spiking / VOLATILE regime) both must agree: noise is high, demand more evidence
        opening minutes   5-minute must agree, 15-minute not against (today's 15-minute bars are still few)
        trend day         (day type / sticky bias TREND or EXPANSION on the signal's side) 15-minute must agree;
                          the 5-minute may be FLAT -- a fresh 1-minute break leads the 5-minute -- but not against
        anything else     both must agree (no day context to lean on)
    """
    want = "UP" if side == "CE" else "DOWN"
    other = "DOWN" if want == "UP" else "UP"
    t15, t5 = a.get("trend15", "FLAT"), a.get("trend5", "FLAT")
    tf = f"15m {t15}, 5m {t5}"
    if fam == "REVERSAL":
        return (None, f"reversal: 5m turned {want} ({tf})") if t5 == want else \
            (f"reversal needs the 5-min to turn {want} first ({tf})", "")
    if fam == "RANGE":
        if t15 == other:
            return f"15-min trend is {t15}, against a range {side} ({tf})", ""
        if t5 == other:
            return f"5-min trend is {t5}, against a range {side} ({tf})", ""
        return None, f"range: neither timeframe against ({tf})"
    dt, bias = a.get("dayType") or {}, a.get("dayBias") or {}
    trend_day = any(x.get("type") in ("TREND", "EXPANSION") and x.get("side") == side for x in (dt, bias))
    vix_chg = (a.get("vix") or {}).get("changePct")
    volatile = a.get("regime") == "VOLATILE" or (vix_chg is not None and vix_chg >= 5)
    opening = ((a.get("session") or {}).get("minutesSinceOpen") or 999) < OPENING_MIN
    if volatile:
        ok = t15 == want and t5 == want
        return (None, f"volatile tape: both agree ({tf})") if ok else (f"volatile tape needs 15m and 5m {want} ({tf})", "")
    if opening:
        ok = t5 == want and t15 != other
        return (None, f"opening: 5m {want}, 15m not against ({tf})") if ok else \
            (f"opening minutes need 5m {want} and 15m not {other} ({tf})", "")
    if trend_day:
        ok = t15 == want and t5 != other
        return (None, f"{side} trend day: 15m {want}, 5m not against ({tf})") if ok else \
            (f"{side} trend day still needs 15m {want} and 5m not {other} ({tf})", "")
    ok = t15 == want and t5 == want
    return (None, f"no trend-day context: 15m and 5m both {want}") if ok else \
        (f"no trend-day context: needs 15m and 5m both {want} ({tf})", "")


def last_entry_block(a: dict[str, Any]) -> str | None:
    """No new INDEX entries from settings.INDEX_LAST_ENTRY_TIME (IST); None for commodities, when off, or before it.
    17 Nov 2026: the last trading hour's entries lost in both halves of the May-Nov replay (late-day momentum,
    wedge breakdowns, noise breakouts that had no time left to run)."""
    from app.core.config.settings import settings  # lazy: keeps this module importable without app config
    from app.modules.opportunity_finder.provider.underlying_config import get_config

    hhmm = (getattr(settings, "INDEX_LAST_ENTRY_TIME", "") or "").strip()
    code = a.get("code") or ""
    cfg = get_config(code) if code else None
    if not hhmm or (cfg is not None and cfg.type != "INDEX"):
        return None
    h, m = (int(x) for x in hhmm.split(":"))
    now_min = (a.get("session") or {}).get("nowMin")
    if now_min is None or now_min < h * 60 + m:
        return None
    return f"no new index entries from {hhmm} IST (last-hour entries lost in both halves of the replay)"


def confirm_timeframes(a: dict[str, Any], found: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep only setups where the timeframes agree on the side:
         15-minute  TREND setups: trend must point the same way (UP for CE, DOWN for PE)
                    RANGE setups: FLAT or the same way; REVERSAL setups: any (see family())
          5-minute  the setup itself is the trigger (already a completed 5-minute bar)
          1-minute  one_minute_check() passes -- always run, for every setup
    Returns (confirmed, rejected) where each rejected item is {name, side, reason}."""
    late = last_entry_block(a)
    if late:
        return [], [{"name": s["name"], "side": s["side"], "reason": late} for s in found]
    trend = a.get("trend15", "FLAT")
    b1 = a.get("bars1") or []
    atr5 = a.get("atr5") or 0.0
    ok: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for s in found:
        ce = s["side"] == "CE"
        reason = None
        info: dict[str, Any] = {}
        want = "UP" if ce else "DOWN"
        fam = family(s["name"])
        block = policy_block(a, s) or day_type_block(a, s)
        why_tf = ""
        if block:
            reason = block
        else:
            reason, why_tf = tf_agreement(a, s["side"], fam)
            if not reason:
                reason, info = one_minute_check(b1, s, atr5)
        if reason:
            rejected.append({"name": s["name"], "side": s["side"], "reason": reason})
        else:
            ok.append({**s, **info, "family": fam, "dayType": (a.get("dayType") or {}).get("type"),
                       "timeframes": {"15m": trend, "5m": a.get("trend5", "FLAT"), "1m": "confirmed",
                                      "signal": s.get("signalTf", "5m"), "why": why_tf},
                       # the evidence behind it, shown on the session's pick: 15-minute trend, 1-minute trigger
                       "timeframeDetail": {
                           "15m": {"trend": trend, "source": a.get("trend15Source") or "none"},
                           "5m": {"trend": a.get("trend5", "FLAT")}, "why": why_tf,
                           "1m": {"close": info.get("entry1m"), "ema9": info.get("ema1m"),
                                  "trigger": info.get("trigger1m")}}})
    return ok, rejected
