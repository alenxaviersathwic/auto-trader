"""
The temporary view of an index, the way a human trader says it out loud:

    "NIFTY temporary view is bearish. Likely down to 24,500. If a 5-min candle closes below 24,500,
     next 24,450. View is wrong on a 5-min close above 24,620."

Built on top of momentum_now.read() (the last ~60 minutes bias) and the levels analyze() already computes.
Pure: takes the analyze() dict + the now-read, returns a small dict, easy to unit-test. No new market calls.

Level ladder (the places price actually reacts at):
  previous-day high/low/close, CPR top/bottom, R1/S1, opening range, initial balance, day high/low,
  option-chain OI walls (CE resistance / PE support), today's 5-minute swing highs/lows (fractals),
  round numbers (step picked from the 5-min ATR: NIFTY ~50, SENSEX/BANKNIFTY ~100).
  Levels closer than 0.25 ATR are merged into one zone (the strongest name leads the label).

Directional view (BULLISH / BEARISH):
  target 1   nearest zone in the bias direction, at least 0.3 ATR away
  target 2   next zone beyond target 1 (at least 0.5 ATR further), conditional on a 5-min close beyond target 1
  wrong      the 30-minute swing extreme against the bias (5-min close beyond it kills the view)
  no zone in reach -> ATR projection (1.5 ATR, then +1 ATR), labelled as such
MIXED view: the range between the nearest support and resistance, with the breakdown and breakout targets.
Confidence: |score| >= 4 HIGH, 3 MEDIUM, else LOW; dropped one step when target 1 is more than 3 ATR away.
"""
from __future__ import annotations

from typing import Any

MIN_GAP_ATR = 0.3  # target 1 must be at least this far from price
NEXT_GAP_ATR = 0.5  # target 2 must be at least this far beyond target 1
MERGE_ATR = 0.25  # levels this close form one zone
SCAN_ATR = 8.0  # ignore levels further than this from price
SWING_WINDOW = 6  # bars that define the "wrong" level (30 minutes of 5-minute bars)
FAR_ATR = 3.0

# name, priority (higher = stronger reaction level)
_LEVELS: dict[str, tuple[str, int]] = {
    "pdh": ("prev-day high", 5), "pdl": ("prev-day low", 5), "pdc": ("prev close", 3),
    "dayHigh": ("day high", 4), "dayLow": ("day low", 4),
    "r1": ("R1", 3), "s1": ("S1", 3), "tc": ("CPR top", 3), "bc": ("CPR bottom", 3), "pivot": ("pivot", 2),
    "orHigh": ("opening-range high", 3), "orLow": ("opening-range low", 3),
    "ibHigh": ("IB high", 3), "ibLow": ("IB low", 3),
}
_ROUND_STEPS = (50.0, 100.0, 250.0, 500.0, 1000.0)


def _fmt(x: float) -> str:
    return f"{x:,.0f}"


def round_step(atr5: float) -> float:
    """Smallest round step at least one 5-min ATR wide (NIFTY ~50, SENSEX / BANKNIFTY ~100)."""
    for s in _ROUND_STEPS:
        if s >= atr5:
            return s
    return _ROUND_STEPS[-1]


def _swings(bars: list[dict[str, Any]]) -> list[tuple[str, float, int]]:
    """Today's 5-minute fractal swing highs/lows (2 bars each side)."""
    out: list[tuple[str, float, int]] = []
    for i in range(2, len(bars) - 2):
        h, l = bars[i]["h"], bars[i]["l"]
        if all(h > bars[j]["h"] for j in (i - 2, i - 1, i + 1, i + 2)):
            out.append(("swing high", h, 3))
        if all(l < bars[j]["l"] for j in (i - 2, i - 1, i + 1, i + 2)):
            out.append(("swing low", l, 3))
    return out


def ladder(a: dict[str, Any], spot: float, atr5: float) -> list[dict[str, Any]]:
    """Merged reaction zones around price, sorted low -> high: {level, label, strength}."""
    raw: list[tuple[str, float, int]] = []
    lv = a.get("levels") or {}
    for k, (name, pr) in _LEVELS.items():
        v = lv.get(k)
        if v:
            raw.append((name, float(v), pr))
    oi = a.get("oi") or {}
    if oi.get("resistance"):
        raw.append(("CE OI wall", float(oi["resistance"]), 5))
    if oi.get("support"):
        raw.append(("PE OI wall", float(oi["support"]), 5))
    raw += _swings(a.get("bars5") or [])
    step = round_step(atr5)
    lo, hi = spot - SCAN_ATR * atr5, spot + SCAN_ATR * atr5
    r = (lo // step) * step
    while r <= hi:
        if r > 0:
            raw.append(("round", r, 3 if r % (2 * step) == 0 else 2))
        r += step

    raw = sorted((x for x in raw if lo <= x[1] <= hi), key=lambda x: x[1])
    tol = max(MERGE_ATR * atr5, spot * 0.0001)
    zones: list[list[tuple[str, float, int]]] = []
    for x in raw:
        if zones and x[1] - zones[-1][0][1] <= tol:
            zones[-1].append(x)
        else:
            zones.append([x])
    out = []
    for z in zones:
        lead = max(z, key=lambda x: (x[2], x[0] != "round"))  # a named level beats a round number on a tie
        names = [lead[0]] + [n for n in dict.fromkeys(x[0] for x in z) if n != lead[0]]
        out.append({"level": round(lead[1], 2), "label": " + ".join(names[:3]), "strength": sum(x[2] for x in z)})
    return out


def _step(level: float, label: str, spot: float, atr5: float, cond: str | None) -> dict[str, Any]:
    d = level - spot
    return {"if": cond, "level": round(level, 2), "label": label, "distance": round(d, 2),
            "distanceAtr": round(d / atr5, 2) if atr5 else None}


def _pick(zones: list[dict[str, Any]], spot: float, atr5: float, down: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    """(target 1, target 2) in the given direction; ATR projections when no zone is in reach."""
    gap, nxt = MIN_GAP_ATR * atr5, NEXT_GAP_ATR * atr5
    sign = -1 if down else 1
    side = sorted((z for z in zones if (z["level"] <= spot - gap if down else z["level"] >= spot + gap)),
                  key=lambda z: abs(z["level"] - spot))
    t1 = side[0] if side else {"level": round(spot + sign * 1.5 * atr5, 2), "label": "ATR projection"}
    beyond = [z for z in side if (z["level"] <= t1["level"] - nxt if down else z["level"] >= t1["level"] + nxt)]
    t2 = beyond[0] if beyond else {"level": round(t1["level"] + sign * atr5, 2), "label": "ATR projection"}
    return t1, t2


def build(a: dict[str, Any], now: dict[str, Any] | None) -> dict[str, Any] | None:
    bars = a.get("bars5") or []
    atr5 = a.get("atr5") or 0.0
    spot = a.get("spot") or (bars[-1]["c"] if bars else None)
    if not now or not spot or not atr5 or len(bars) < SWING_WINDOW:
        return None
    zones = ladder(a, float(spot), atr5)
    bias, score = now["bias"], abs(now.get("score") or 0)
    word = {"BULLISH": "bullish", "BEARISH": "bearish", "MIXED": "sideways"}[bias]
    head = f"Temporary view ({now.get('minutes', 60)} min) is {word}."

    if bias == "MIXED":
        s1, s2 = _pick(zones, spot, atr5, down=True)
        r1, r2 = _pick(zones, spot, atr5, down=False)
        steps = [_step(s2["level"], s2["label"], spot, atr5, f"5-min close below {_fmt(s1['level'])}"),
                 _step(r2["level"], r2["label"], spot, atr5, f"5-min close above {_fmt(r1['level'])}")]
        text = (f"{head} Range {_fmt(s1['level'])} ({s1['label']}) to {_fmt(r1['level'])} ({r1['label']}). "
                f"Below {_fmt(s1['level'])} it can go to {_fmt(s2['level'])}; above {_fmt(r1['level'])} "
                f"it can go to {_fmt(r2['level'])}.")
        return {"bias": bias, "confidence": "LOW", "spot": round(spot, 2), "text": text,
                "range": {"support": _step(s1["level"], s1["label"], spot, atr5, None),
                          "resistance": _step(r1["level"], r1["label"], spot, atr5, None)},
                "steps": steps, "invalidation": None}

    down = bias == "BEARISH"
    t1, t2 = _pick(zones, spot, atr5, down)
    recent = bars[-SWING_WINDOW:]
    wrong = max(b["h"] for b in recent) if down else min(b["l"] for b in recent)
    wrong_label = f"30-min swing {'high' if down else 'low'}"
    if (wrong - spot) * (1 if down else -1) < MIN_GAP_ATR * atr5:
        wrong, wrong_label = spot + (atr5 if down else -atr5), "1 ATR stop"

    conf = "HIGH" if score >= 4 else "MEDIUM" if score == 3 else "LOW"
    if abs(t1["level"] - spot) > FAR_ATR * atr5:
        conf = {"HIGH": "MEDIUM", "MEDIUM": "LOW", "LOW": "LOW"}[conf]
    near = "Likely" if conf != "LOW" else "Can"
    move, beyond, against = ("down", "below", "above") if down else ("up", "above", "below")
    text = (f"{head} {near} {'go ' if near == 'Can' else ''}{move} to {_fmt(t1['level'])} ({t1['label']}). "
            f"If a 5-min candle closes {beyond} {_fmt(t1['level'])}, next {_fmt(t2['level'])} ({t2['label']}). "
            f"View is wrong on a 5-min close {against} {_fmt(wrong)} ({wrong_label}).")
    return {"bias": bias, "confidence": conf, "spot": round(spot, 2), "text": text, "range": None,
            "steps": [_step(t1["level"], t1["label"], spot, atr5, None),
                      _step(t2["level"], t2["label"], spot, atr5, f"5-min close {beyond} {_fmt(t1['level'])}")],
            "invalidation": _step(wrong, wrong_label, spot, atr5, f"5-min close {against} {_fmt(wrong)}")}
