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
  GAP_GO           gap >= 0.3% that holds (gap unfilled), continuation bar             first 90 minutes
  PCR_SHIFT        option-chain PCR drift + put/call OI writing, price confirms         any regime
  SHORT_COVERING_SPIKE  futures price up + OI down + volume spike (mirror: long unwinding)  any regime

Raw setups come from detect(); confirm_timeframes() then keeps only those where the 15-minute trend, the 5-minute
trigger and the 1-minute entry bar all agree.

Futures OI buildup confirms (+1) or contradicts (-1, flagged) each signal; volume spike adds +1.
"""

from typing import Any

from app.modules.opportunities.service.market_analysis import next_level

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

    # 11. Opening gap that holds (gap-and-go): continuation bar while the gap stays unfilled
    gap, pdc, day_o = lv.get("gapPct"), lv.get("pdc"), lv.get("dayOpen")
    since_open = (a.get("session") or {}).get("minutesSinceOpen", 0)
    if gap is not None and pdc and day_o and abs(gap) >= 0.3 and 15 <= since_open <= 90:
        if gap > 0 and lv.get("dayLow", 0) > pdc and last["c"] > day_o and green and last["c"] > prev["h"]:
            add("GAP_GO", "CE", max(day_o, min(last["l"], prev["l"])) - tick, 3, f"gap-up {gap:+.2f}% holding above the previous close")
        if gap < 0 and lv.get("dayHigh", 0) < pdc and last["c"] < day_o and red and last["c"] < prev["l"]:
            add("GAP_GO", "PE", min(day_o, max(last["h"], prev["h"])) + tick, 3, f"gap-down {gap:+.2f}% holding below the previous close")

    # 12. PCR / option-OI shift: puts being written (PCR rising) = support building -> CE; calls written -> PE
    sh = a.get("oiShift")
    if sh:
        if sh["pcrChg"] >= 0.08 and sh["peOiChgPct"] > sh["ceOiChgPct"] + 1.0 and green:
            add("PCR_SHIFT", "CE", last["l"] - tick, 2, f"PCR rose {sh['pcrChg']:+.2f} to {sh['pcr']}, put OI {sh['peOiChgPct']:+.1f}% vs call OI {sh['ceOiChgPct']:+.1f}%")
        if sh["pcrChg"] <= -0.08 and sh["ceOiChgPct"] > sh["peOiChgPct"] + 1.0 and red:
            add("PCR_SHIFT", "PE", last["h"] + tick, 2, f"PCR fell {sh['pcrChg']:+.2f} to {sh['pcr']}, call OI {sh['ceOiChgPct']:+.1f}% vs put OI {sh['peOiChgPct']:+.1f}%")

    # 13. Short-covering spike (CE) / long-unwinding spike (PE): price and OI move opposite, on a volume spike
    bu = a.get("buildup") or {}
    if spike:
        if bu.get("state") == "SHORT_COVERING" and bu.get("oiChgPct", 0) <= -0.15 and green:
            add("SHORT_COVERING_SPIKE", "CE", last["l"] - tick, 3, f"futures up {bu['priceChgPct']:+.2f}% with OI {bu['oiChgPct']:+.2f}% on a volume spike")
        if bu.get("state") == "LONG_UNWINDING" and bu.get("oiChgPct", 0) <= -0.15 and red:
            add("SHORT_COVERING_SPIKE", "PE", last["h"] + tick, 3, f"futures down {bu['priceChgPct']:+.2f}% with OI {bu['oiChgPct']:+.2f}% on a volume spike (long unwinding)")
    return out


# ───────────────────────── multi-timeframe confirmation ─────────────────────────
def confirm_timeframes(a: dict[str, Any], found: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep only setups where all three timeframes agree on the side:
         15-minute  trend must point the same way (UP for CE, DOWN for PE)
          5-minute  the setup itself is the trigger (already a completed 5-minute bar)
          1-minute  the last completed 1-minute bar closes with the trade and does not give back the prior close
    Returns (confirmed, rejected) where each rejected item is {name, side, reason}."""
    trend = a.get("trend15", "FLAT")
    b1 = a.get("bars1") or []
    ok: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for s in found:
        ce = s["side"] == "CE"
        reason = None
        if trend != ("UP" if ce else "DOWN"):
            reason = f"15-min trend is {trend}, needs {'UP' if ce else 'DOWN'}"
        elif len(b1) < 2:
            reason = "no completed 1-minute bars for the entry check"
        else:
            l1, p1 = b1[-1], b1[-2]
            agrees = (l1["c"] > l1["o"] and l1["c"] >= p1["c"]) if ce else (l1["c"] < l1["o"] and l1["c"] <= p1["c"])
            if not agrees:
                reason = f"1-min entry bar does not confirm ({'bullish' if ce else 'bearish'} close needed)"
        if reason:
            rejected.append({"name": s["name"], "side": s["side"], "reason": reason})
        else:
            ok.append({**s, "timeframes": {"15m": trend, "5m": s["name"], "1m": "confirmed"}})
    return ok, rejected
