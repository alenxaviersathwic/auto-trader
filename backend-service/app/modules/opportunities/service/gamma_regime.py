"""
Dealer-gamma regime (GEX proxy) from the live option chain -- the quantitative answer to "what moves the market"
(11 Nov 2026 institutional review, Strategy 3). Pure functions.

  When option dealers are net LONG gamma they hedge by selling rallies / buying dips -> intraday mean reversion,
  lower realised vol (good for short premium). Net SHORT gamma -> they chase moves -> intraday momentum
  (Baltussen et al. JFE 2021; Dim-Eraker-Vilkov; Barbon & Buraschi). US effect is real but small (Cboe: net 0DTE
  market-maker gamma ~0.04-0.17% of S&P futures liquidity) -- expect a tilt, never a "pin".

  GEX_k = gamma_k x OI_k x S^2 x 1%  ("rupees of delta to hedge per 1% move"); OI is taken in units of the underlying
  (pass `oi_units` = lot size if a feed reports contracts instead).
  Sign convention (India has no public dealer book): DEFAULT = customers long puts / short calls, so dealers are
  long calls (+) and short puts (-). participant_signs() replaces it with what NSE participant-wise OI says the
  CLIENT side holds: dealers are assumed to hold the opposite of clients.

  regime(): POSITIVE / NEGATIVE / NEUTRAL by tercile of today's value within the underlying's own recent history.
  route():  POSITIVE -> short premium allowed, momentum SHORTS (PE) blocked; NEGATIVE -> momentum only, no short
            premium; NEUTRAL -> both. Live use is behind settings.GAMMA_ROUTER_ENABLED, which stays False until
            scripts/validate_gamma_regime.py shows the negative tercile has significantly more continuation (t > 2).
"""
import math
from datetime import datetime
from typing import Any

_SQRT_2PI = math.sqrt(2 * math.pi)
MIN_HISTORY = 30


def bs_gamma(spot: float, strike: float, iv_pct: float, t_years: float) -> float:
    if spot <= 0 or strike <= 0 or iv_pct <= 0 or t_years <= 0:
        return 0.0
    v = iv_pct / 100 * math.sqrt(t_years)
    d1 = (math.log(spot / strike) + 0.5 * v * v) / v
    return math.exp(-0.5 * d1 * d1) / _SQRT_2PI / (spot * v)


def years_to_expiry(expiry: str, now: datetime, close_hhmm: tuple[int, int] = (15, 30)) -> float:
    exp = datetime.fromisoformat(expiry).replace(hour=close_hhmm[0], minute=close_hhmm[1], tzinfo=now.tzinfo)
    minutes = max(1.0, (exp - now).total_seconds() / 60)
    return minutes / (252 * 375)  # trading-minute clock, same as the replay scripts


def net_gex(chain: dict[str, Any], spot: float, now: datetime, call_sign: int = 1, put_sign: int = -1,
            oi_units: float = 1.0) -> float:
    """Dealer net gamma exposure, rupees of hedge per 1% move (sign: + long gamma / - short gamma).
    `oi_units` multiplies the chain OI into units of the underlying (1.0 when the feed already reports units)."""
    t = years_to_expiry(chain["expiry"], now)
    total = 0.0
    for r in chain.get("strikes") or []:
        k = float(r["strike"])
        for side, sign in (("CE", call_sign), ("PE", put_sign)):
            leg = r.get(side) or {}
            iv, oi = leg.get("iv") or 0.0, leg.get("oi") or 0.0
            total += sign * bs_gamma(spot, k, iv, t) * oi * oi_units * spot * spot * 0.01
    return total


def participant_signs(client: dict[str, float] | None) -> tuple[int, int]:
    """(call_sign, put_sign) for dealers = opposite of the NSE 'Client' category's net option position.
    `client` = {"callLong", "callShort", "putLong", "putShort"} index-option contracts; None -> default convention."""
    if not client:
        return 1, -1
    net_calls = client.get("callLong", 0) - client.get("callShort", 0)
    net_puts = client.get("putLong", 0) - client.get("putShort", 0)
    return (-1 if net_calls > 0 else 1), (-1 if net_puts > 0 else 1)


def regime(value: float, history: list[float]) -> str | None:
    """POSITIVE / NEUTRAL / NEGATIVE by tercile within `history` (same underlying, comparable times); None if short."""
    if len(history) < MIN_HISTORY:
        return None
    h = sorted(history)
    lo, hi = h[len(h) // 3], h[(2 * len(h)) // 3]
    return "POSITIVE" if value >= hi else "NEGATIVE" if value <= lo else "NEUTRAL"


def route(reg: str | None) -> dict[str, bool]:
    """What the regime allows. Unknown regime -> no restriction (the noise-area day type still applies)."""
    if reg == "POSITIVE":
        return {"shortPremium": True, "momentumLong": True, "momentumShort": False}
    if reg == "NEGATIVE":
        return {"shortPremium": False, "momentumLong": True, "momentumShort": True}
    return {"shortPremium": True, "momentumLong": True, "momentumShort": True}
