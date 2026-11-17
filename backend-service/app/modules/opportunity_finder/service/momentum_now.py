"""
The "now" read of an index: what the last ~60 minutes say, separate from the whole-day read.

Why (17 Nov 2026): at 15:07 SENSEX had fallen from 82,800 (14:30) to 82,578, yet the index view said BULLISH. Every
input it used was a whole-day or older read -- the morning's TREND day call, price vs the opening noise area,
yesterday's FII positioning -- so it could not see an afternoon sell-off. This read uses only recent 5-minute bars
and the futures VWAP. Pure: takes the `analyze()` dict, returns a small dict, easy to unit-test.

Votes (+1 bullish / -1 bearish / 0 neutral):
  5-min EMAs     close vs EMA9 vs EMA21 stacked up / down
  VWAP           futures above / below the day's VWAP (skipped with no futures volume)
  Last 60 min    close change over 12 bars, in 5-min ATRs: >= +0.75 ATR up, <= -0.75 ATR down
  Structure      last 6 bars: a higher high and higher low vs the 3 before / lower high and lower low
  Off the high   <= -1 when price is >= 1.5 ATR below the day high after making it in the last 90 min
                 (and the mirror off the day low); a fresh reversal the EMAs are still catching up to
Score >= +2 BULLISH, <= -2 BEARISH, else MIXED.
"""
from __future__ import annotations

from typing import Any

from app.modules.opportunity_finder.service.market_analysis import ema

LOOKBACK_BARS = 12  # 60 minutes of 5-minute bars
MOVE_ATR = 0.75
OFF_EXTREME_ATR = 1.5
RECENT_EXTREME_BARS = 18  # the extreme must be from the last 90 minutes to count as a turn


def read(a: dict[str, Any]) -> dict[str, Any] | None:
    bars = a.get("bars5") or []
    if len(bars) < 6:
        return None
    closes = [b["c"] for b in bars]
    last = closes[-1]
    atr5 = a.get("atr5") or 0.0
    votes: list[dict[str, Any]] = []

    if len(closes) >= 9:
        e9, e21 = ema(closes, 9)[-1], ema(closes, 21)[-1]
        v = 1 if last > e9 > e21 else -1 if last < e9 < e21 else 0
        votes.append({"label": "5-min EMAs", "vote": v,
                      "value": f"close {last:,.0f} · EMA9 {e9:,.0f} · EMA21 {e21:,.0f}"})

    vw = a.get("vwap") or {}
    if vw.get("value"):
        v = 1 if vw.get("above") else -1
        votes.append({"label": "VWAP", "vote": v,
                      "value": f"futures {'above' if v > 0 else 'below'} VWAP ({vw.get('distPct', 0):+.2f}%)"})

    n = min(LOOKBACK_BARS, len(closes) - 1)
    chg = last - closes[-1 - n]
    chg_atr = chg / atr5 if atr5 else 0.0
    v = 1 if chg_atr >= MOVE_ATR else -1 if chg_atr <= -MOVE_ATR else 0
    votes.append({"label": f"Last {n * 5} min", "vote": v,
                  "value": f"{chg:+,.0f} pts ({chg / closes[-1 - n] * 100:+.2f}%, {chg_atr:+.1f} ATR)"})

    if len(bars) >= 6:
        a3, b3 = bars[-6:-3], bars[-3:]
        hh, hl = max(x["h"] for x in b3) > max(x["h"] for x in a3), min(x["l"] for x in b3) > min(x["l"] for x in a3)
        lh, ll = max(x["h"] for x in b3) < max(x["h"] for x in a3), min(x["l"] for x in b3) < min(x["l"] for x in a3)
        v = 1 if hh and hl else -1 if lh and ll else 0
        votes.append({"label": "Structure (30 min)", "vote": v,
                      "value": "higher highs and lows" if v > 0 else "lower highs and lows" if v < 0 else "overlapping"})

    if atr5:
        recent = bars[-RECENT_EXTREME_BARS:]
        hi_i = max(range(len(recent)), key=lambda i: recent[i]["h"])
        lo_i = min(range(len(recent)), key=lambda i: recent[i]["l"])
        hi, lo = recent[hi_i]["h"], recent[lo_i]["l"]
        off_hi, off_lo = (hi - last) / atr5, (last - lo) / atr5
        if off_hi >= OFF_EXTREME_ATR and hi_i > lo_i:
            votes.append({"label": "Off the high", "vote": -1, "value": f"{hi - last:,.0f} pts below the 90-min high {hi:,.0f}"})
        elif off_lo >= OFF_EXTREME_ATR and lo_i > hi_i:
            votes.append({"label": "Off the low", "vote": 1, "value": f"{last - lo:,.0f} pts above the 90-min low {lo:,.0f}"})

    score = sum(x["vote"] for x in votes)
    return {"bias": "BULLISH" if score >= 2 else "BEARISH" if score <= -2 else "MIXED", "score": score,
            "change": round(chg, 2), "changePct": round(chg / closes[-1 - n] * 100, 3), "minutes": n * 5,
            "votes": votes}
