"""
Option-chain sub-agent: reads the MCX chain the desk would actually trade -- the nearest expiry that does not expire
today (the menu never buys the expiring series). MCX has no chain API; the chain is built from the instrument file +
live quotes + greeks (opportunity_finder/provider/upstox_market_data.py), so every number here is a live quote.

  PCR          >= 1.3 put writers dominate (support under price, +1); <= 0.7 call writers dominate (-1)
  OI walls     the biggest call OI at/above price (resistance) and put OI at/below (support), in ATR5 from price
  liquidity    ATM call / put spread <= 3% of mid with sellers on the ask; both sides illiquid -> BLOCK
  IV           ATM implied volatility (average of call and put)
`path_note()` tells the head trader when a wall sits inside a setup's path to target. Walls are strikes on THAT
chain's own future; a setup's levels are on the front future, so the calendar spread is added before comparing.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
MAX_SPREAD_PCT = 3.0


def _spread_pct(leg: dict[str, Any]) -> float | None:
    bid, ask = leg.get("bid") or 0.0, leg.get("ask") or 0.0
    if bid <= 0 or ask <= 0:
        return None
    return (ask - bid) / ((ask + bid) / 2) * 100


def pick_chain(market: dict[str, Any], now: datetime | None = None) -> dict[str, Any] | None:
    today = (now or datetime.now(IST)).astimezone(IST).date().isoformat()
    chains = [c for c in market.get("chains") or [] if c.get("strikes")]
    return next((c for c in chains if c.get("expiry") != today), chains[0] if chains else None)


def read(market: dict[str, Any], atr5: float, now: datetime | None = None) -> dict[str, Any]:
    ch = pick_chain(market, now)
    if not ch:
        return {"agent": "options", "name": "Option chain", "stance": "BLOCK", "score": 0,
                "summary": "no option chain with live quotes", "facts": ["no option chain with live quotes"], "data": {}}
    spot = float(ch.get("spot") or market.get("spot") or 0)
    atm = min(ch["strikes"], key=lambda s: abs(s["strike"] - spot))
    liq = {}
    for side in ("CE", "PE"):
        leg = atm.get(side) or {}
        sp = _spread_pct(leg)
        liq[side] = {"spreadPct": None if sp is None else round(sp, 2), "ok": sp is not None and sp <= MAX_SPREAD_PCT
                     and (leg.get("askQty") or 0) > 0, "ltp": leg.get("ltp")}
    ivs = [x for x in ((atm.get("CE") or {}).get("iv"), (atm.get("PE") or {}).get("iv")) if x]
    iv = round(sum(ivs) / len(ivs), 2) if ivs else None
    pcr = ch.get("pcr")
    score = 1 if pcr is not None and pcr >= 1.3 else -1 if pcr is not None and pcr <= 0.7 else 0
    facts = [f"trading expiry {ch['expiry']} on its future at {spot:,.1f}; ATM {atm['strike']:g}"]
    if pcr is not None:
        facts.append(f"PCR {pcr:.2f}" + (" (put writers support price)" if score > 0 else
                                          " (call writers cap price)" if score < 0 else ""))
    res, sup = ch.get("resistance"), ch.get("support")
    if res:
        facts.append(f"call-OI wall {res:g}" + (f" ({(res - spot) / atr5:.1f} ATR above)" if atr5 else ""))
    if sup:
        facts.append(f"put-OI wall {sup:g}" + (f" ({(spot - sup) / atr5:.1f} ATR below)" if atr5 else ""))
    for side in ("CE", "PE"):
        l = liq[side]
        facts.append(f"ATM {side} spread {l['spreadPct']}%" + ("" if l["ok"] else " - too wide / no sellers"))
    if iv:
        facts.append(f"ATM IV {iv}%")
    stance = "BLOCK" if not liq["CE"]["ok"] and not liq["PE"]["ok"] else (
        "BULLISH" if score > 0 else "BEARISH" if score < 0 else "NEUTRAL")
    summary = facts[1] if len(facts) > 1 else facts[0]
    if stance == "BLOCK":
        summary = "ATM options too illiquid to trade (spread / no sellers)"
    return {"agent": "options", "name": "Option chain", "stance": stance, "score": score, "summary": summary,
            "facts": facts, "data": {"expiry": ch["expiry"], "chainSpot": spot, "atm": atm["strike"], "pcr": pcr,
                                     "resistance": res, "support": sup, "iv": iv, "liquidity": liq}}


def path_note(c: dict[str, Any], report: dict[str, Any], front_spot: float) -> str | None:
    """A wall inside the first 60% of a setup's way to its target (translated onto the front future)."""
    d = report.get("data") or {}
    shift = (d.get("chainSpot") or front_spot) - front_spot  # calendar spread: chain future - front future
    up = c["side"] == "CE"
    wall = d.get("resistance") if up else d.get("support")
    if not wall:
        return None
    w = wall - shift
    path = abs(c["target"] - c["entry"]) * 0.6
    if (c["entry"] < w < c["entry"] + path) if up else (c["entry"] - path < w < c["entry"]):
        return f"{'call' if up else 'put'}-OI wall {wall:g} sits inside the way to the target"
    return None


def liquid(report: dict[str, Any], side: str) -> bool:
    return bool(((report.get("data") or {}).get("liquidity") or {}).get(side, {}).get("ok"))
