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
               trader (trade_history/service/trader_brain.py) steps the target on to the 1.272 / 1.618 extensions.

The pocket alone is a retail chart pattern, so three independent confirmations are REQUIRED, all from real data:
  Price   (the 5-minute candles themselves, _price_action_check)
  action  a) the pullback is CORRECTIVE: it took at least MIN_PULLBACK_BARS bars and none of its bars has a body as big
             as the impulse's biggest body (an impulsive drop into the pocket is a reversal, not a pullback);
          b) the market REJECTS the pocket with a classic signal bar on the last or the previous bar:
             - pin bar / hammer: the wick into the pocket is >= PIN_WICK_BODY x the body and >= PIN_WICK_RANGE of the
               bar, the close in the top PIN_CLOSE_ZONE of the bar, the wick tip inside the 0.45-0.786 zone;
             - engulfing: the turn bar's body engulfs the previous (pullback-direction) body;
             - inside-bar break: the previous bar sits inside the one before it and the turn bar closes beyond it.
  OI      (option chain, analysis["oi"])     no OI wall inside the first WALL_PATH_SHARE of the way to the target, and
          either the opposite wall sits behind the pocket (put wall under a CE pocket) or futures OI buildup agrees
          (LONG_BUILDUP / SHORT_COVERING for CE).
  Volume  (futures 5-minute bars)            the pullback traded on less volume than the impulse, and the turn bar's
          volume is at least the average of the prior bars (analysis["volume"]["ratio5m"] >= MIN_TURN_VOLUME_RATIO).

Replays (backtests) have no option-chain history and the index candles carry no futures volume, so with
analysis["replay"] true the OI and volume checks report "not replayable" and do not block; price action still must
pass. A backtest of this setup therefore measures the price-action version only (see docs/11-traders-module.md).

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
STOP_RETRACE = 0.786        # invalidation: the stop is never placed beyond this level
STOP_BUFFER_ATR = 0.15      # stop = just beyond the pocket's rejection extreme by this much ATR5 (17 Nov 2026)
MIN_RR = 1.3
WALL_PATH_SHARE = 0.6       # an OI wall inside the first 60% of entry -> target blocks the trade
MIN_TURN_VOLUME_RATIO = 1.0
# price action (17 Nov 2026)
MIN_PULLBACK_BARS = 2       # a one-bar drop into the pocket is not a pullback
PIN_WICK_BODY = 2.0         # pin bar: rejection wick >= 2x the body ...
PIN_WICK_RANGE = 0.5        # ... and >= half of the bar's range
PIN_CLOSE_ZONE = 0.4        # close in the top 40% of the bar (bottom 40% for PE)
PIN_ZONE = (0.45, 0.786)    # the wick tip must reach into the pocket and stay above the invalidation


def _body(b: dict[str, Any]) -> float:
    return abs(b["c"] - b["o"])


def _pin(b: dict[str, Any], up: bool, lvl) -> bool:
    """Pin bar / hammer (shooting star for PE) whose rejection wick tip sits inside the pocket zone."""
    rng = b["h"] - b["l"]
    if rng <= 0:
        return False
    wick = (min(b["o"], b["c"]) - b["l"]) if up else (b["h"] - max(b["o"], b["c"]))
    close_pos = (b["c"] - b["l"]) / rng if up else (b["h"] - b["c"]) / rng
    tip = b["l"] if up else b["h"]
    lo_lvl, hi_lvl = sorted((lvl(PIN_ZONE[0]), lvl(PIN_ZONE[1])))
    return (wick >= PIN_WICK_BODY * max(_body(b), 1e-9) and wick >= PIN_WICK_RANGE * rng
            and close_pos >= 1 - PIN_CLOSE_ZONE and lo_lvl <= tip <= hi_lvl)


def _price_action_check(window: list[dict[str, Any]], start: int, end: int, up: bool, lvl) -> tuple[bool, str, str | None]:
    """(ok, why, pattern) for the candles of the pullback and the turn: corrective pullback + a rejection signal."""
    impulse, pull = window[start:end + 1], window[end + 1:]
    last, prev = window[-1], window[-2]
    if len(pull) < MIN_PULLBACK_BARS:
        return False, f"pullback only {len(pull)} bar(s): a drop, not a correction", None
    with_trend = [_body(b) for b in impulse if (b["c"] > b["o"]) == up]
    against = [_body(b) for b in pull[:-1] if (b["c"] < b["o"]) == up]
    if with_trend and against and max(against) >= max(with_trend):
        return False, (f"impulsive pullback: a {max(against):.1f}-point {'red' if up else 'green'} body vs the "
                       f"impulse's biggest {max(with_trend):.1f}"), None
    pattern = None
    if _pin(last, up, lvl) or _pin(prev, up, lvl):
        pattern = "PIN_BAR"
    elif ((prev["c"] < prev["o"]) == up and _body(prev) > 0
          and (last["c"] >= prev["o"] and last["o"] <= prev["c"] if up else last["c"] <= prev["o"] and last["o"] >= prev["c"])):
        pattern = "ENGULFING"
    elif len(window) >= 3:
        mother = window[-3]
        inside = prev["h"] <= mother["h"] and prev["l"] >= mother["l"]
        if inside and (last["c"] > prev["h"] if up else last["c"] < prev["l"]):
            pattern = "INSIDE_BAR_BREAK"
    if not pattern:
        return False, "no rejection candle at the pocket (pin bar, engulfing or inside-bar break)", None
    label = {"PIN_BAR": "pin bar" if up else "shooting star", "ENGULFING": "bullish engulfing" if up else "bearish engulfing",
             "INSIDE_BAR_BREAK": "inside-bar break"}[pattern]
    return True, f"{label} at the pocket after a {len(pull) - 1}-bar corrective pullback", pattern


def _swings(bars: list[dict[str, Any]], up: bool) -> list[tuple[int, int]]:
    """Every candidate impulse inside `bars`, NEWEST first, as (start index, end index).

    The swing ends are local highs (above the bar before) not exceeded since (CE) / the mirror for PE, walking back
    from the bar before the turn bar; each start is the opposite extreme of the up-to-MAX_IMPULSE_BARS leg before its end.
    17 Nov 2026: only the 3-hour extreme was ever considered, so every smaller leg + pullback after the day's high
    was invisible (6-month replay: ~1,370 swings per index reached the pocket, the old code saw a fraction)."""
    n = len(bars)
    if n < 6:
        return []
    out: list[tuple[int, int]] = []
    best = None
    for end in range(n - 2, 0, -1):  # the last bar is the turn bar, never the swing extreme
        v = bars[end]["h"] if up else bars[end]["l"]
        if best is not None and not (v > best if up else v < best):
            continue
        best = v
        # a real local extreme: beyond the bar before it too (not just a bar that trails the actual high/low)
        if not (v > bars[end - 1]["h"] if up else v < bars[end - 1]["l"]):
            continue
        # the impulse starts after the last bar that was already beyond this end (an older, higher high for CE):
        # a leg to 140 cannot start before a 141 high
        first = max(0, end - MAX_IMPULSE_BARS)
        for j in range(end - 1, first - 1, -1):
            if (bars[j]["h"] >= v) if up else (bars[j]["l"] <= v):
                first = j + 1
                break
        leg = range(first, end + 1)
        start = min(leg, key=lambda i: bars[i]["l"]) if up else max(leg, key=lambda i: bars[i]["h"])
        if start < end:
            out.append((start, end))
    return out


def _swing(bars: list[dict[str, Any]], up: bool) -> tuple[int, int] | None:
    """The biggest swing in the window (the 3-hour extreme): the oldest entry of _swings()."""
    sw = _swings(bars, up)
    return sw[-1] if sw else None


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
        found = None
        for start, end in _swings(window, up):  # newest swing first; the first one that sets up wins
            lo, hi = (window[start]["l"], window[end]["h"]) if up else (window[end]["l"], window[start]["h"])
            move = hi - lo
            if move < MIN_IMPULSE_ATR * atr5:
                continue
            pull = window[end + 1:]
            if up:
                ext_i = min(range(len(pull)), key=lambda i: pull[i]["l"])
                extreme = pull[ext_i]["l"]
                depth = (hi - extreme) / move
                lvl = lambda r, hi=hi, move=move: hi - r * move  # noqa: E731 -- price at retracement r
                turned = last["c"] > last["o"] and last["c"] > prev["c"] and last["c"] > lvl(0.618)
            else:
                ext_i = max(range(len(pull)), key=lambda i: pull[i]["h"])
                extreme = pull[ext_i]["h"]
                depth = (extreme - lo) / move
                lvl = lambda r, lo=lo, move=move: lo + r * move  # noqa: E731
                turned = last["c"] < last["o"] and last["c"] < prev["c"] and last["c"] < lvl(0.618)
            if not (POCKET_MIN <= depth <= POCKET_MAX) or len(pull) - 1 - ext_i >= FRESH_BARS or not turned:
                continue
            entry = last["c"]
            # stop just beyond the pocket's rejection extreme, never beyond the 0.786 invalidation (17 Nov 2026: the
            # fixed 0.786 stop failed reward:risk on 44% of real pockets -- a strong turn candle ate the reward)
            invalid = lvl(STOP_RETRACE) - tick if up else lvl(STOP_RETRACE) + tick
            pocket_stop = extreme - STOP_BUFFER_ATR * atr5 if up else extreme + STOP_BUFFER_ATR * atr5
            stop = max(pocket_stop, invalid) if up else min(pocket_stop, invalid)
            target = hi if up else lo
            risk = (entry - stop) if up else (stop - entry)
            reward = (target - entry) if up else (entry - target)
            if risk <= 0 or reward <= 0 or reward / risk < MIN_RR:
                continue
            found = (start, end, lo, hi, move, depth, lvl, entry, stop, target, risk, reward)
            break
        if not found:
            continue
        start, end, lo, hi, move, depth, lvl, entry, stop, target, risk, reward = found
        pa_ok, pa_why, pattern = _price_action_check(window, start, end, up, lvl)
        if a.get("replay"):  # backtest: no option-chain history, no futures volume on index candles
            oi_ok, oi_why = None, "not replayable (no option-chain history)"
            vol_ok, vol_why = None, "not replayable (no futures volume in the replay)"
        else:
            oi_ok, oi_why = _oi_check(a, up, entry, stop, target, atr5)
            vol_ok, vol_why = _volume_check(a, window, start, end)
        ext = (lambda r: lo + r * move) if up else (lambda r: hi - r * move)
        side = "CE" if up else "PE"
        failed = [w for ok, w in ((pa_ok, f"price action: {pa_why}"), (oi_ok, f"OI: {oi_why}"),
                                  (vol_ok, f"volume: {vol_why}")) if ok is False]
        block = "Fib pocket not confirmed: " + "; ".join(failed) if failed else None
        out.append({
            "name": NAME, "side": side, "strength": 3,
            "reason": (f"pullback to the {depth:.2f} retracement of the {lo:.1f} -> {hi:.1f} swing "
                       f"({move / atr5:.1f} ATR) turned back {'up' if up else 'down'}; price action: {pa_why}; OI: {oi_why}; "
                       f"volume: {vol_why}"),
            "entry": round(entry, 2), "stop": round(stop, 2), "target": round(target, 2),
            "targetLevel": "Fib 1.0 (swing " + ("high" if up else "low") + ")", "rr": round(reward / risk, 2),
            "stopBasis": "0.786 invalidation" if stop == (lvl(STOP_RETRACE) - tick if up else lvl(STOP_RETRACE) + tick)
                         else "just beyond the pocket's rejection " + ("low" if up else "high"),
            "confirmBlock": block, "oiConfirmed": oi_ok, "volumeConfirmed": vol_ok,
            "priceActionConfirmed": pa_ok, "priceAction": {"pattern": pattern, "why": pa_why},
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
        "oiConfirm": s.get("oiConfirmed"), "volumeConfirm": s.get("volumeConfirmed"),
        "priceActionConfirm": s.get("priceActionConfirmed"), "priceActionPattern": (s.get("priceAction") or {}).get("pattern"),
        "why": s.get("reason"),
    }


# ───────────────────────── watch: what the Fib trader is waiting for (17 Nov 2026) ─────────────────────────
def watch(bars: list[dict[str, Any]], atr5: float) -> list[dict[str, Any]]:
    """Where each side stands on the way to a Fib golden-pocket signal, for the index view (no signal is made here):
      NO_SWING    no impulse of MIN_IMPULSE_ATR x ATR5 in the window yet
      SHALLOW     impulse found, pullback has not reached the pocket: waiting for price to come into 0.50-0.618
      IN_POCKET   price is in the pocket: waiting for a rejection candle (pin bar / engulfing / inside-bar break)
      STALE       the pocket was reached but more than FRESH_BARS bars ago without a turn
      FAILED      the pullback went past the 0.786 invalidation: this swing is done
    One entry per side; the side whose impulse is more recent is listed first."""
    out: list[dict[str, Any]] = []
    if atr5 <= 0 or len(bars) < 6:
        return [{"side": s, "stage": "NO_SWING", "text": "not enough 5-minute bars yet"} for s in ("CE", "PE")]
    window = bars[-LOOKBACK_BARS:]
    for up in (True, False):
        side = "CE" if up else "PE"
        sw = _swing(window, up)
        if not sw:
            out.append({"side": side, "stage": "NO_SWING", "text": f"no {'up' if up else 'down'} impulse yet"})
            continue
        # the swing the detector would use: the newest big-enough one whose pullback has not gone past the pocket;
        # if every one has, the newest big-enough one (shown as FAILED); else the biggest (shown as NO_SWING)
        big = [(s0, e0) for s0, e0 in _swings(window, up)
               if (window[e0]["h"] - window[s0]["l"] if up else window[s0]["h"] - window[e0]["l"]) >= MIN_IMPULSE_ATR * atr5]

        def _depth(s0: int, e0: int) -> float:
            lo0, hi0 = (window[s0]["l"], window[e0]["h"]) if up else (window[e0]["l"], window[s0]["h"])
            p0 = window[e0 + 1:]
            x0 = (min(b["l"] for b in p0) if up else max(b["h"] for b in p0)) if p0 else (hi0 if up else lo0)
            return ((hi0 - x0) if up else (x0 - lo0)) / (hi0 - lo0)

        alive = [x for x in big if _depth(*x) <= POCKET_MAX]
        start, end = alive[0] if alive else big[0] if big else sw
        lo, hi = (window[start]["l"], window[end]["h"]) if up else (window[end]["l"], window[start]["h"])
        move = hi - lo
        if move < MIN_IMPULSE_ATR * atr5:
            out.append({"side": side, "stage": "NO_SWING", "endAt": window[end]["t"],
                        "text": f"biggest {'up' if up else 'down'} move {move:.0f} pts = {move / atr5:.1f} ATR "
                                f"(needs {MIN_IMPULSE_ATR:g} ATR)"})
            continue
        lvl = (lambda r: hi - r * move) if up else (lambda r: lo + r * move)
        pull = window[end + 1:]
        ext = (min(b["l"] for b in pull) if up else max(b["h"] for b in pull)) if pull else (hi if up else lo)
        depth = ((hi - ext) if up else (ext - lo)) / move
        last = window[-1]["c"]
        now_depth = ((hi - last) if up else (last - lo)) / move
        pocket = sorted((round(lvl(0.5), 2), round(lvl(0.618), 2)))
        base = {"side": side, "swingLow": round(lo, 2), "swingHigh": round(hi, 2), "move": round(move, 2),
                "depth": round(depth, 3), "nowDepth": round(now_depth, 3), "pocket": pocket,
                "invalidation": round(lvl(STOP_RETRACE), 2), "endAt": window[end]["t"]}
        swing = f"{lo:.0f} -> {hi:.0f}" if up else f"{hi:.0f} -> {lo:.0f}"
        pocket_txt = f"{pocket[0]:,.0f}-{pocket[1]:,.0f}"
        if depth > POCKET_MAX:
            stage, text = "FAILED", (f"pullback went to the {depth:.2f} retracement of {swing}, past the pocket: "
                                     f"this swing is done")
        elif depth >= POCKET_MIN and len(pull) - 1 - (
                min(range(len(pull)), key=lambda i: pull[i]["l"]) if up
                else max(range(len(pull)), key=lambda i: pull[i]["h"])) >= FRESH_BARS:
            stage, text = "STALE", f"reached the pocket {pocket_txt} earlier but did not turn; waiting for a new swing"
        elif depth >= POCKET_MIN:
            stage, text = "IN_POCKET", (f"price is in the pocket {pocket_txt} of {swing}: waiting for a rejection "
                                        f"candle (pin bar, engulfing or inside-bar break)")
        else:
            stage, text = "SHALLOW", (f"pullback only {depth:.2f} of {swing}: waiting for price to come back into "
                                      f"the pocket {pocket_txt}")
        out.append({**base, "stage": stage, "text": text})
    order = {"IN_POCKET": 0, "SHALLOW": 1, "STALE": 2, "FAILED": 3, "NO_SWING": 4}
    return sorted(out, key=lambda w: (order[w["stage"]], -(w.get("move") or 0)))
