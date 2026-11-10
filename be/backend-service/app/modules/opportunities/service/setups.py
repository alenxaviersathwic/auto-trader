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

Day type (service/day_type.py) decides which setups may trade at all (confirm_timeframes()):
  PIN / RANGE        only REVERSAL and RANGE-family setups (theta beats trend-following inside the noise area)
  TREND / EXPANSION  TREND-family setups on the day's side, plus REVERSAL; no VWAP band fades

Setup families decide what the 15-minute trend must say (confirm_timeframes()):
  TREND     needs the 15-minute trend on its side (a FLAT 15-min trend is no trend to follow)
  RANGE     the 15-minute trend may be FLAT or on its side, never against it
  REVERSAL  FAILED_BREAK_RECLAIM: may go against a 15-minute trend -- a reclaimed level is how a V-day turns
A FLAT 15-minute trend used to veto every setup; on a V-reversal day (NIFTY/SENSEX, 9 Nov 2026) that removed all of
them while a discretionary trader traded the reclaim. The 5-minute trigger and the 1-minute chart still must agree:
one_minute_check() is ALWAYS run (1-min EMA9 side, no fresh 1-min swing against the trade, setup stop not touched,
not chasing, target not already hit).

Futures OI buildup confirms (+1) or contradicts (-1, flagged) each signal; volume spike adds +1.
"""

from typing import Any

from app.modules.opportunities.service.market_analysis import ema, next_level

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


def detect(a: dict[str, Any], cfg: Any) -> list[dict[str, Any]]:
    bars = a.get("bars5") or []
    if len(bars) < 3:
        return []
    lv = a.get("levels") or {}
    atr5 = a.get("atr5") or 0.0
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
    fb = a.get("futBars5") or []
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
    if noise.get("prevState") == "INSIDE" and noise.get("state") in ("ABOVE", "BELOW"):
        if noise["state"] == "ABOVE" and green:
            add("NOISE_BREAKOUT", "CE", min(last["l"], noise["upper"]) - tick, 3 + spike,
                f"5-min close {last['c']:.1f} above the noise area {noise['upper']:.1f} (move is no longer noise)")
        if noise["state"] == "BELOW" and red:
            add("NOISE_BREAKOUT", "PE", max(last["h"], noise["lower"]) + tick, 3 + spike,
                f"5-min close {last['c']:.1f} below the noise area {noise['lower']:.1f} (move is no longer noise)")

    # 17. Late-day momentum: first half hour and the whole day point the same way, price outside the noise area.
    sess = a.get("session") or {}
    fh, pdc2 = a.get("firstHalfHourRetPct"), lv.get("pdc")
    if fh is not None and pdc2 and LATE_MOMO_MIN_TO_CLOSE[0] <= sess.get("minutesToClose", 0) <= LATE_MOMO_MIN_TO_CLOSE[1]:
        day_ret = (last["c"] - pdc2) / pdc2 * 100
        recent = bars[-3:]
        if fh > 0 and day_ret > 0 and noise.get("state") == "ABOVE" and green:
            add("LATE_DAY_MOMENTUM", "CE", min(b["l"] for b in recent) - tick, 3,
                f"first half hour {fh:+.2f}% and day {day_ret:+.2f}% both up, above the noise area into the close")
        if fh < 0 and day_ret < 0 and noise.get("state") == "BELOW" and red:
            add("LATE_DAY_MOMENTUM", "PE", max(b["h"] for b in recent) + tick, 3,
                f"first half hour {fh:+.2f}% and day {day_ret:+.2f}% both down, below the noise area into the close")
    return out


# ───────────────────────── multi-timeframe confirmation ─────────────────────────
RANGE_SETUPS = {"PDH_PDL_RETEST", "OI_WALL_REJECT", "VWAP_BAND_REVERT"}  # PCR_SHIFT demoted 10 Nov 2026
REVERSAL_SETUPS = {"FAILED_BREAK_RECLAIM"}
LATE_MOMO_MIN_TO_CLOSE = (35, 70)  # 14:30-15:05 on a 15:40 close


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
    if not kind:
        return None
    fam = family(s["name"])
    if kind in ("PIN", "RANGE"):
        if fam == "TREND":
            return f"{kind} day (price inside the noise area): trend/breakout setups are not traded"
        return None
    if s["name"] == "VWAP_BAND_REVERT":
        return f"{kind} day: no VWAP fades against an expanding move"
    if fam == "TREND" and dt.get("side") and s["side"] != dt["side"]:
        return f"{kind} day is on the {dt['side']} side"
    return None


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


def confirm_timeframes(a: dict[str, Any], found: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep only setups where the timeframes agree on the side:
         15-minute  TREND setups: trend must point the same way (UP for CE, DOWN for PE)
                    RANGE setups: FLAT or the same way; REVERSAL setups: any (see family())
          5-minute  the setup itself is the trigger (already a completed 5-minute bar)
          1-minute  one_minute_check() passes -- always run, for every setup
    Returns (confirmed, rejected) where each rejected item is {name, side, reason}."""
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
        block = day_type_block(a, s)
        if block:
            reason = block
        elif fam == "TREND" and trend != want:
            reason = f"15-min trend is {trend}, needs {want}"
        elif fam == "RANGE" and trend not in (want, "FLAT"):
            reason = f"15-min trend is {trend}, against a {s['name']} {s['side']}"
        else:
            reason, info = one_minute_check(b1, s, atr5)
        if reason:
            rejected.append({"name": s["name"], "side": s["side"], "reason": reason})
        else:
            ok.append({**s, **info, "family": fam, "dayType": (a.get("dayType") or {}).get("type"),
                       "timeframes": {"15m": trend, "5m": s["name"], "1m": "confirmed"}})
    return ok, rejected
