"""
FIB_GOLDEN_POCKET: the one setup the Fib Golden-Pocket Trader takes (pure code, no I/O).

CE (PE is the mirror):
  1. Impulse   a swing low -> swing high on completed 5-minute bars, at least MIN_IMPULSE_ATR x ATR5 tall and at most
               MAX_IMPULSE_BARS long, inside the last LOOKBACK_BARS bars.
  2. Pullback  after the high, price retraces into the 0.50-0.618 pocket (deepest point between POCKET_MIN and
               POCKET_MAX of the swing, i.e. it reached the pocket and never got near the 0.786 invalidation). The
               deepest point is recent (last FRESH_BARS bars).
  3. Turn      the last 5-minute bar closes green, above the previous close and back above the 0.618 level.
  Plan         entry = last close, stop = just beyond the 0.786 retracement, target = the swing high (1.0). The live
               trader (trades/service/trader_brain.py) steps the target on to the 1.272 / 1.618 extensions.

The pocket alone is a retail chart pattern, so two independent confirmations are REQUIRED, both from real data:
  OI      (option chain, analysis["oi"])     no OI wall inside the first WALL_PATH_SHARE of the way to the target, and
          either the opposite wall sits behind the pocket (put wall under a CE pocket) or futures OI buildup agrees
          (LONG_BUILDUP / SHORT_COVERING for CE).
  Volume  (futures 5-minute bars)            the pullback traded on less volume than the impulse, and the turn bar's
          volume is at least the average of the prior bars (analysis["volume"]["ratio5m"] >= MIN_TURN_VOLUME_RATIO).

A pocket that is found but not confirmed is still returned, with `confirmBlock` set to the reason, so the funnel
report shows why it did not trade. `setups.policy_block()` rejects any signal that carries a `confirmBlock`.

NOT BACKTESTED YET (added 16 Nov 2026). Run scripts/backtest_range_real.py over the stored months before trusting it
with size; every other setup in SETUP_POLICY earned its place that way.
"""
from typing import Any

NAME = "FIB_GOLDEN_POCKET"
LOOKBACK_BARS = 36          # 3 hours of 5-minute bars
MAX_IMPULSE_BARS = 18       # the impulse leg itself: at most 90 minutes
MIN_IMPULSE_ATR = 3.0       # swing height in ATR5
POCKET_MIN, POCKET_MAX = 0.46, 0.70  # deepest retracement allowed: reached ~0.50, stayed clear of 0.786
FRESH_BARS = 3              # the pullback extreme must be within the last 3 bars
STOP_RETRACE = 0.786
MIN_RR = 1.3
WALL_PATH_SHARE = 0.6       # an OI wall inside the first 60% of entry -> target blocks the trade
MIN_TURN_VOLUME_RATIO = 1.0


def _swing(bars: list[dict[str, Any]], up: bool) -> tuple[int, int] | None:
    """(start index, end index) of the impulse inside `bars`: for CE the swing low then the swing high."""
    n = len(bars)
    if n < 6:
        return None
    body = range(n - 1)  # the last bar is the turn bar, never the swing extreme
    end = max(body, key=lambda i: bars[i]["h"]) if up else min(body, key=lambda i: bars[i]["l"])
    if end > n - 2 or end < 1:
        return None
    leg = range(max(0, end - MAX_IMPULSE_BARS), end + 1)
    start = min(leg, key=lambda i: bars[i]["l"]) if up else max(leg, key=lambda i: bars[i]["h"])
    return (start, end) if start < end else None


def _oi_check(a: dict[str, Any], up: bool, entry: float, stop: float, target: float, atr5: float) -> tuple[bool, str]:
    oi = a.get("oi") or {}
    sup, res = oi.get("support"), oi.get("resistance")
    if not sup and not res:
        return False, "no option-chain OI data"
    wall, wall_name = (res, "call") if up else (sup, "put")
    path = abs(target - entry) * WALL_PATH_SHARE
    if wall and ((entry < wall < entry + path) if up else (entry - path < wall < entry)):
        return False, f"{wall_name}-OI wall {wall:.0f} blocks the way to the target {target:.1f}"
    back, back_name = (sup, "put") if up else (res, "call")
    backed = bool(back) and ((stop - atr5 <= back <= entry + 0.25 * atr5) if up
                             else (entry - 0.25 * atr5 <= back <= stop + atr5))
    bu = (a.get("buildup") or {}).get("state")
    flow = bu in (("LONG_BUILDUP", "SHORT_COVERING") if up else ("SHORT_BUILDUP", "LONG_UNWINDING"))
    if backed:
        return True, f"{back_name}-OI wall {back:.0f} sits behind the pocket" + (f", futures {bu}" if flow else "")
    if flow:
        return True, f"futures {bu}, no OI wall in the way"
    return False, f"no {back_name}-OI wall behind the pocket and futures show {bu or 'no buildup'}"


def _volume_check(a: dict[str, Any], bars: list[dict[str, Any]], start: int, end: int) -> tuple[bool, str]:
    vol = a.get("volume") or {}
    ratio = vol.get("ratio5m")
    fut = {b["t"]: float(b.get("v") or 0.0) for b in (a.get("futBars5") or [])}
    if ratio is None or not any(fut.values()):
        return False, "no futures volume data"
    if ratio < MIN_TURN_VOLUME_RATIO:
        return False, f"turn bar volume only {ratio:.2f}x the average"
    imp = [fut[b["t"]] for b in bars[start:end + 1] if fut.get(b["t"])]
    pull = [fut[b["t"]] for b in bars[end + 1:-1] if fut.get(b["t"])]
    if imp and pull:
        imp_avg, pull_avg = sum(imp) / len(imp), sum(pull) / len(pull)
        if pull_avg > imp_avg:
            return False, f"pullback volume {pull_avg / imp_avg:.2f}x the impulse volume (sellers active)"
        return True, f"pullback on {pull_avg / imp_avg:.2f}x the impulse volume, turn bar {ratio:.2f}x average"
    return True, f"turn bar {ratio:.2f}x average volume"


def detect(a: dict[str, Any], bars: list[dict[str, Any]], atr5: float, tick: float) -> list[dict[str, Any]]:
    """Fib golden-pocket signals on the last completed 5-minute bar (at most one per side)."""
    out: list[dict[str, Any]] = []
    if atr5 <= 0 or len(bars) < 6:
        return out
    window = bars[-LOOKBACK_BARS:]
    last, prev = window[-1], window[-2]
    for up in (True, False):
        sw = _swing(window, up)
        if not sw:
            continue
        start, end = sw
        lo, hi = (window[start]["l"], window[end]["h"]) if up else (window[end]["l"], window[start]["h"])
        move = hi - lo
        if move < MIN_IMPULSE_ATR * atr5:
            continue
        pull = window[end + 1:]
        if up:
            ext_i = min(range(len(pull)), key=lambda i: pull[i]["l"])
            depth = (hi - pull[ext_i]["l"]) / move
            lvl = lambda r: hi - r * move  # noqa: E731 -- price at retracement r
            turned = last["c"] > last["o"] and last["c"] > prev["c"] and last["c"] > lvl(0.618)
        else:
            ext_i = max(range(len(pull)), key=lambda i: pull[i]["h"])
            depth = (pull[ext_i]["h"] - lo) / move
            lvl = lambda r: lo + r * move  # noqa: E731
            turned = last["c"] < last["o"] and last["c"] < prev["c"] and last["c"] < lvl(0.618)
        if not (POCKET_MIN <= depth <= POCKET_MAX) or len(pull) - 1 - ext_i >= FRESH_BARS or not turned:
            continue
        entry = last["c"]
        stop = lvl(STOP_RETRACE) - tick if up else lvl(STOP_RETRACE) + tick
        target = hi if up else lo
        risk = (entry - stop) if up else (stop - entry)
        reward = (target - entry) if up else (entry - target)
        if risk <= 0 or reward <= 0 or reward / risk < MIN_RR:
            continue
        oi_ok, oi_why = _oi_check(a, up, entry, stop, target, atr5)
        vol_ok, vol_why = _volume_check(a, window, start, end)
        ext = (lambda r: lo + r * move) if up else (lambda r: hi - r * move)
        side = "CE" if up else "PE"
        block = None if oi_ok and vol_ok else "Fib pocket not confirmed: " + "; ".join(
            w for ok, w in ((oi_ok, f"OI: {oi_why}"), (vol_ok, f"volume: {vol_why}")) if not ok)
        out.append({
            "name": NAME, "side": side, "strength": 3,
            "reason": (f"pullback to the {depth:.2f} retracement of the {lo:.1f} -> {hi:.1f} swing "
                       f"({move / atr5:.1f} ATR) turned back {'up' if up else 'down'}; OI: {oi_why}; volume: {vol_why}"),
            "entry": round(entry, 2), "stop": round(stop, 2), "target": round(target, 2),
            "targetLevel": "Fib 1.0 (swing " + ("high" if up else "low") + ")", "rr": round(reward / risk, 2),
            "confirmBlock": block, "oiConfirmed": oi_ok, "volumeConfirmed": vol_ok,
            "fib": {"swingLow": round(lo, 2), "swingHigh": round(hi, 2), "depth": round(depth, 3),
                    "fib500": round(lvl(0.5), 2), "fib618": round(lvl(0.618), 2), "fib786": round(lvl(0.786), 2),
                    "fib1272": round(ext(1.272), 2), "fib1618": round(ext(1.618), 2)},
        })
    return out


def setup_meta(s: dict[str, Any], spot: float, ltp: float, delta: float) -> dict[str, Any] | None:
    """What the trade needs to keep from a Fib signal: the real swing and its Fibonacci levels on the underlying, and
    the same levels as option-premium prices for one contract (premium = ltp + |delta| x underlying move in the
    trade's favour -- the same delta conversion the menu uses for the stop and target). Saved on the opportunity, the
    session pick and the trade, so the trade screen and the Fib trader's extension targets come from the chart swing
    instead of multiples of the planned move. None for any other setup."""
    fib = s.get("fib")
    if s.get("name") != NAME or not fib or not ltp or not spot:
        return None
    up = s["side"] == "CE"
    d = abs(float(delta or 0.0)) or 0.5

    def prem(level: float) -> float:
        move = (level - spot) if up else (spot - level)
        return round(max(0.05, ltp + d * move), 2)

    target_key, far_key = ("swingHigh", "swingLow") if up else ("swingLow", "swingHigh")
    return {
        "kind": NAME, "side": s["side"], "spotAtSignal": round(float(spot), 2), "premiumAtSignal": round(float(ltp), 2),
        "delta": round(d, 3), "depth": fib.get("depth"),
        "underlying": {k: fib[k] for k in ("swingLow", "swingHigh", "fib500", "fib618", "fib786", "fib1272", "fib1618")},
        "premium": {"swingStart": prem(fib[far_key]), "fib100": prem(fib[target_key]), "fib500": prem(fib["fib500"]),
                    "fib618": prem(fib["fib618"]), "fib786": prem(fib["fib786"]), "fib1272": prem(fib["fib1272"]),
                    "fib1618": prem(fib["fib1618"])},
        "oiConfirm": s.get("oiConfirmed"), "volumeConfirm": s.get("volumeConfirmed"), "why": s.get("reason"),
    }
