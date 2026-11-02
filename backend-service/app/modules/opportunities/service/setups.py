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
