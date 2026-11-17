"""
Price-structure sub-agent: reads the 1-, 5- and 15-minute futures charts like a desk trader and proposes concrete
setups. Pure: takes the scan's `analyze()` dict, never fetches anything.

Stance (votes +1 / -1): 15-minute trend, 5-minute EMA9 > EMA21 stack, futures vs VWAP, the last-hour read
(momentum_now). >= +2 BULLISH, <= -2 BEARISH, else NEUTRAL.

Setups (CE shown; PE is the mirror). Levels are on the futures price, which is what MCX options follow:
  DESK_TREND_PULLBACK  15-minute trend up, futures above VWAP, one of the last three 5-minute bars dipped into the
                       value zone (VWAP / 5-min EMA20, within 0.3 ATR5) without breaking 1 ATR5 below it, and the last
                       1-minute bar closed above the previous 1-minute high and its 1-minute EMA9.
                       Stop 0.25 ATR5 under the pullback low; target 2R (or the day high when that is further).
  DESK_RANGE_BREAK     the last 5-minute bar is the FIRST close above everything before it today (by 0.1 ATR5),
                       with a body-strong bar (range >= 1 ATR5, close in its top 30%) and the 15-minute trend not down;
                       entry only within 0.6 ATR5 of the broken level (no chasing). Stop 0.5 ATR5 back inside; 2R.
  DESK_FIB_POCKET      fib_pocket.detect() when its price-action check passed; its OI / volume confirmations are
                       passed on for the head trader to weigh.
A setup is only proposed with risk between 0.5 and 2.5 ATR5 and reward:risk >= 1.5.
"""
from __future__ import annotations

from typing import Any

from app.modules.opportunity_finder.service import fib_pocket, momentum_now
from app.modules.opportunity_finder.service import setups as engine_setups
from app.modules.opportunity_finder.service.market_analysis import ema

MIN_RR = 1.5
RISK_ATR = (0.5, 2.5)


def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), 2)


def _stance(a: dict[str, Any], now: dict[str, Any] | None) -> tuple[int, list[str]]:
    score, facts = 0, []
    t = a.get("trend15")
    if t in ("UP", "DOWN"):
        score += 1 if t == "UP" else -1
        facts.append(f"15-min trend {t.lower()}")
    else:
        facts.append("15-min trend flat")
    e = a.get("ema5") or {}
    if e.get("ema9") and e.get("ema21"):
        up = e["ema9"] > e["ema21"]
        score += 1 if up else -1
        facts.append(f"5-min EMA9 {'above' if up else 'below'} EMA21")
    vw = a.get("vwap") or {}
    if vw.get("value"):
        score += 1 if vw.get("above") else -1
        facts.append(f"futures {'above' if vw.get('above') else 'below'} VWAP ({vw.get('distPct', 0):+.2f}%)")
    if now:
        score += 1 if now["bias"] == "BULLISH" else -1 if now["bias"] == "BEARISH" else 0
        facts.append(f"last {now['minutes']} min {now['change']:+,.1f} ({now['bias'].lower()})")
    n = a.get("noise") or {}
    if n.get("state"):
        facts.append(f"{'inside' if n['state'] == 'INSIDE' else n['state'].lower() + ' of'} the day's noise band "
                     f"{n.get('lower', 0):,.1f}-{n.get('upper', 0):,.1f}")
    return score, facts


def _plan(name: str, side: str, entry: float, stop: float, target: float, atr5: float, why: str,
          extra: dict[str, Any] | None = None) -> dict[str, Any] | None:
    up = side == "CE"
    risk = (entry - stop) if up else (stop - entry)
    reward = (target - entry) if up else (entry - target)
    if risk <= 0 or reward <= 0 or not (RISK_ATR[0] * atr5 <= risk <= RISK_ATR[1] * atr5) or reward / risk < MIN_RR:
        return None
    return {"name": name, "side": side, "entry": _r(entry), "stop": _r(stop), "target": _r(target),
            "rr": round(reward / risk, 2), "riskAtr": round(risk / atr5, 2), "why": why, **(extra or {})}


def _pullback(a: dict[str, Any], up: bool, atr5: float) -> dict[str, Any] | None:
    b5, b1 = a.get("bars5") or [], a.get("bars1") or []
    e = a.get("ema5") or {}
    vw = (a.get("vwap") or {})
    if len(b5) < 6 or len(b1) < 12 or not e.get("ema20") or a.get("trend15") != ("UP" if up else "DOWN"):
        return None
    if vw.get("value") and bool(vw.get("above")) != up:
        return None
    zone = [z for z in (e.get("ema20"), vw.get("value")) if z]
    recent = b5[-3:]
    ext = min(b["l"] for b in recent) if up else max(b["h"] for b in recent)
    touched = any((ext <= z + 0.3 * atr5) if up else (ext >= z - 0.3 * atr5) for z in zone)
    held = all((ext >= z - 1.0 * atr5) if up else (ext <= z + 1.0 * atr5) for z in zone)
    if not (touched and held):
        return None
    c1 = [b["c"] for b in b1]
    e9 = ema(c1, 9)[-1]
    last, prev = b1[-1], b1[-2]
    trig = (last["c"] > prev["h"] and last["c"] > e9) if up else (last["c"] < prev["l"] and last["c"] < e9)
    if not trig:
        return None
    entry = last["c"]
    stop = ext - 0.25 * atr5 if up else ext + 0.25 * atr5
    risk = abs(entry - stop)
    lv = a.get("levels") or {}
    far = lv.get("dayHigh") if up else lv.get("dayLow")
    target = entry + 2 * risk if up else entry - 2 * risk
    if far and ((far > target) if up else (far < target)):
        target = far
    side = "CE" if up else "PE"
    return _plan("DESK_TREND_PULLBACK", side, entry, stop, target, atr5,
                 f"15-min trend {'up' if up else 'down'}, pullback to the 5-min value zone "
                 f"({ext:,.1f}) held, 1-min close {entry:,.1f} {'above' if up else 'below'} the prior 1-min "
                 f"{'high' if up else 'low'}", {"family": "TREND"})


def _breakout(a: dict[str, Any], up: bool, atr5: float) -> dict[str, Any] | None:
    b5, b1 = a.get("bars5") or [], a.get("bars1") or []
    if len(b5) < 13 or not b1 or a.get("trend15") == ("DOWN" if up else "UP"):
        return None
    before, bar = b5[:-1], b5[-1]
    level = max(b["h"] for b in before) if up else min(b["l"] for b in before)
    prev_c = before[-1]["c"]
    rng = bar["h"] - bar["l"]
    if rng < atr5 or rng <= 0:
        return None
    strong = (bar["c"] - bar["l"]) / rng >= 0.7 if up else (bar["h"] - bar["c"]) / rng >= 0.7
    fresh = (bar["c"] > level + 0.1 * atr5 and prev_c <= level) if up else (bar["c"] < level - 0.1 * atr5 and prev_c >= level)
    entry = b1[-1]["c"]
    near = abs(entry - level) <= 0.6 * atr5
    if not (strong and fresh and near):
        return None
    stop = level - 0.5 * atr5 if up else level + 0.5 * atr5
    risk = abs(entry - stop)
    target = entry + 2 * risk if up else entry - 2 * risk
    return _plan("DESK_RANGE_BREAK", "CE" if up else "PE", entry, stop, target, atr5,
                 f"first 5-min close {'above' if up else 'below'} the day's range {level:,.1f} on a strong bar "
                 f"({rng / atr5:.1f} ATR); entry {entry:,.1f} still within 0.6 ATR of the level",
                 {"family": "TREND", "level": _r(level)})


def _fib(a: dict[str, Any], atr5: float, tick: float) -> list[dict[str, Any]]:
    out = []
    for s in fib_pocket.detect(a, a.get("bars5") or [], atr5, tick):
        if not s.get("priceActionConfirmed"):
            continue
        conf = []
        for k, label in (("oiConfirmed", "OI"), ("volumeConfirmed", "volume")):
            conf.append(f"{label} {'confirms' if s.get(k) else 'does not confirm' if s.get(k) is False else 'n/a'}")
        p = _plan("DESK_FIB_POCKET", s["side"], s["entry"], s["stop"], s["target"], atr5,
                  f"{s['priceAction']['why']} in the {s['fib']['depth']:.2f} pocket of "
                  f"{s['fib']['swingLow']:,.1f}-{s['fib']['swingHigh']:,.1f}; " + ", ".join(conf),
                  {"family": "TREND", "fib": s["fib"], "oiConfirmed": s.get("oiConfirmed"),
                   "volumeConfirmed": s.get("volumeConfirmed")})
        if p:
            out.append(p)
    return out


def read(a: dict[str, Any], tick: float = 0.05) -> dict[str, Any]:
    atr5 = float(a.get("atr5") or 0.0)
    now = momentum_now.read(a)
    score, facts = _stance(a, now)
    stance = "BULLISH" if score >= 2 else "BEARISH" if score <= -2 else "NEUTRAL"
    cands: list[dict[str, Any]] = []
    if atr5 > 0:
        for up in (True, False):
            for fn in (_pullback, _breakout):
                c = fn(a, up, atr5)
                if c:
                    cands.append(c)
        cands += _fib(a, atr5, tick)
    for i, c in enumerate(cands, 1):
        c["id"] = f"c{i}"
        c["withStructure"] = (c["side"] == "CE" and score > 0) or (c["side"] == "PE" and score < 0)
        # the engine's situational 5m / 15m confirmation (setups.tf_agreement), the same judgement for every trader
        block, why = engine_setups.tf_agreement(a, c["side"], "TREND")
        c["tfBlock"], c["tfWhy"] = block, why
    summary = (f"{stance.lower()} structure (score {score:+d}): " + "; ".join(facts[:3])) if facts else "no data"
    return {"agent": "structure", "name": "Price structure", "stance": stance, "score": score, "summary": summary,
            "facts": facts, "data": {"atr5": round(atr5, 2), "now": now, "spot": _r(a.get("spot"))},
            "candidates": cands}
