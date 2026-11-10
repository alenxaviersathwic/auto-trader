"""
Human-Like Position Trader Brain (`trader_brain.py`).

Pure functions (no I/O, 100% deterministic & unit-testable) that evaluate one active option trade
on every tick using:
  1. Historical win-rate / confidence tier:
     - HIGH_CONVICTION (winRatePct >= 75% or confidence >= 80):
         Waits until 80% of target progress (e.g., 28 on 20 -> 30) before locking SL at 50% profit (25),
         giving the setup room to breathe through early noise.
     - STEP_GUARD (winRatePct < 75%, e.g., ~50% win-rate):
         Protects capital early in steps:
           * At 50% of target progress (25 on 20 -> 30): trails SL to +30% of planned move (23, above breakeven + costs).
           * At 80% of target progress (28 on 20 -> 30): trails SL to +50% of planned move (25).
  2. Live 1-minute option premium candle & volume microstructure:
     - Checks volume expansion (`volumeRatio`), candle body vs rejection wicks (`candleStructure`),
       1m ATR, and higher-low support.
  3. Dynamic Target Trailing & Runner Mode:
     - When `ltp >= currentTarget` (e.g. hits 30 and goes beyond):
       * If momentum & volume are strong (`momentumState == "STRONG"` or `volumeRatio >= 1.15` without climax rejection):
         Instead of blindly exiting at 30, locks `currentStop` at `30` (the achieved target) and expands
         `currentTarget` upward so the runner captures the full move.
       * If momentum stalls at target (weak volume / upper rejection wick):
         Exits immediately at `ltp` (`TARGET_HIT`).
  4. Invariant: `currentStop` NEVER moves down; it only ratchets up.
"""
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

TICK = 0.05
HIGH_CONVICTION_WIN_RATE = 75.0


def round_tick(price: float) -> float:
    """Round an option price to the nearest 0.05 tick."""
    return round(round(price / TICK) * TICK, 2)


def select_profile(win_rate_pct: float, confidence: int) -> str:
    """Choose `HIGH_CONVICTION` when historical win-rate >= 75% (or confidence >= 80), else `STEP_GUARD`."""
    if float(win_rate_pct) >= HIGH_CONVICTION_WIN_RATE or int(confidence) >= 80:
        return "HIGH_CONVICTION"
    return "STEP_GUARD"


def analyze_premium_candles(candles_1m: list[dict[str, Any]], ltp: float) -> dict[str, Any]:
    """
    Inspects recent 1-minute option premium candles `[{'t', 'o', 'h', 'l', 'c', 'v'}, ...]`
    and returns live microstructure signals used by the Trader brain:
      - `volumeRatio`: latest bar volume vs rolling average of prior 5 bars
      - `candleStructure`: 'BULLISH_DRIVE' | 'REJECTION_WICK' | 'HIGHER_LOWS' | 'BEARISH_ENGULF' | 'NEUTRAL'
      - `momentumState`: 'STRONG' | 'STEADY' | 'FADING' | 'REVERSING'
      - `atr1m`: average 1-minute range over recent bars
      - `supportLow`: previous completed 1m candle's low (for runner trailing)
    """
    if not candles_1m:
        return {
            "volumeRatio": 1.0,
            "candleStructure": "NEUTRAL",
            "momentumState": "STEADY",
            "atr1m": round(max(0.5, ltp * 0.03), 2),
            "supportLow": None,
            "upperWickRatio": 0.0,
        }

    recent = candles_1m[-8:]
    last = recent[-1]
    prev = recent[-2] if len(recent) >= 2 else last

    # 1m ATR
    ranges = [max(0.05, float(b["h"]) - float(b["l"])) for b in recent]
    atr_1m = sum(ranges) / len(ranges)

    # Volume ratio vs prior completed bars
    prior_vols = [float(b.get("v") or 0.0) for b in recent[:-1] if float(b.get("v") or 0.0) > 0]
    avg_vol = sum(prior_vols) / len(prior_vols) if prior_vols else 0.0
    cur_vol = float(last.get("v") or 0.0)
    vol_ratio = round(cur_vol / avg_vol, 2) if avg_vol > 0 and cur_vol > 0 else 1.0

    # Candle anatomy of latest bar (or previous completed bar if latest just opened)
    bar = last if (float(last["h"]) - float(last["l"])) >= atr_1m * 0.35 else prev
    o, h, l, c = float(bar["o"]), float(bar["h"]), float(bar["l"]), float(bar["c"])
    span = max(0.05, h - l)
    body = c - o
    upper_wick = h - max(o, c)
    upper_wick_ratio = round(upper_wick / span, 2)

    higher_lows = (
        len(recent) >= 3
        and float(recent[-1]["l"]) >= float(recent[-2]["l"]) >= float(recent[-3]["l"])
    )

    if upper_wick_ratio >= 0.58 and body <= span * 0.25:
        structure = "REJECTION_WICK"
    elif body >= span * 0.55 and c >= o:
        structure = "BULLISH_DRIVE"
    elif body <= -span * 0.55:
        structure = "BEARISH_ENGULF"
    elif higher_lows and ltp >= c:
        structure = "HIGHER_LOWS"
    else:
        structure = "NEUTRAL"

    if structure == "BULLISH_DRIVE" and vol_ratio >= 1.15:
        momentum = "STRONG"
    elif structure == "HIGHER_LOWS" and vol_ratio >= 0.95:
        momentum = "STRONG"
    elif structure == "REJECTION_WICK" and vol_ratio < 0.9:
        momentum = "FADING"
    elif structure == "BEARISH_ENGULF":
        momentum = "REVERSING"
    else:
        momentum = "STEADY"

    support_low = round_tick(float(prev["l"])) if len(recent) >= 2 else None
    return {
        "volumeRatio": vol_ratio,
        "candleStructure": structure,
        "momentumState": momentum,
        "atr1m": round(atr_1m, 2),
        "supportLow": support_low,
        "upperWickRatio": upper_wick_ratio,
    }


@dataclass(frozen=True)
class BrainDecision:
    action: str  # HOLD | TRAIL_SL | TRAIL_BOTH | TRAIL_TARGET | EXIT
    newStop: float
    newTarget: float
    exitReason: str | None
    exitPrice: float | None
    reason: str
    telemetry: dict[str, Any]


def evaluate_tick(
    *,
    entry_at: float,
    initial_stop: float,
    initial_target: float,
    current_stop: float,
    current_target: float,
    peak_price: float,
    ltp: float,
    trader_profile: str,
    candles_1m: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    close_at: datetime | None = None,
) -> BrainDecision:
    """
    Evaluates the live option price (`ltp`) and 1-minute option premium candles (`candles_1m`)
    against the trade's entry, stop, target, and `trader_profile` (`HIGH_CONVICTION` vs `STEP_GUARD`).
    """
    entry_at = float(entry_at)
    initial_stop = float(initial_stop)
    initial_target = float(initial_target)
    current_stop = float(current_stop)
    current_target = float(current_target)
    ltp = float(ltp)
    peak = max(float(peak_price), ltp, entry_at)

    planned_move = max(0.05, initial_target - entry_at)
    progress_pct = round((peak - entry_at) / planned_move * 100.0, 1)
    live_progress_pct = round((ltp - entry_at) / planned_move * 100.0, 1)

    micro = analyze_premium_candles(candles_1m or [], ltp)
    risk_now = max(0.05, ltp - current_stop)
    reward_now = max(0.0, current_target - ltp)
    rr_now = round(reward_now / risk_now, 2)
    telemetry = {
        **micro,
        "progressPct": progress_pct,
        "liveProgressPct": live_progress_pct,
        "rrNow": rr_now,
        "peakPrice": round(peak, 2),
        "inRunnerMode": peak >= initial_target,
    }

    # 1. Hard Session Close Guard
    if now is not None and close_at is not None and now >= close_at:
        return BrainDecision(
            action="EXIT",
            newStop=current_stop,
            newTarget=current_target,
            exitReason="SESSION_CLOSE",
            exitPrice=ltp,
            reason=f"Session trading hours ended; squared off at ₹{ltp:.2f}",
            telemetry=telemetry,
        )

    # 2. Stop-Loss / Trailing Stop-Loss Hit
    if ltp <= current_stop:
        is_trailed = current_stop > initial_stop + 1e-6
        exit_reason = "TRAILING_STOP_HIT" if is_trailed else "STOP_HIT"
        label = "Trailing SL" if is_trailed else "Initial SL"
        return BrainDecision(
            action="EXIT",
            newStop=current_stop,
            newTarget=current_target,
            exitReason=exit_reason,
            exitPrice=ltp,
            reason=f"{label} ₹{current_stop:.2f} touched at LTP ₹{ltp:.2f}",
            telemetry=telemetry,
        )

    new_stop = current_stop
    new_target = current_target
    reasons: list[str] = []

    # 3. Target Reached or Exceeded (`ltp >= current_target`)
    if ltp >= current_target:
        # Check if live momentum & volume justify extending the target into a runner
        can_run = micro["momentumState"] == "STRONG" or (
            micro["momentumState"] == "STEADY"
            and micro["candleStructure"] != "REJECTION_WICK"
            and micro["volumeRatio"] >= 1.0
        )
        if not can_run:
            return BrainDecision(
                action="EXIT",
                newStop=current_stop,
                newTarget=current_target,
                exitReason="TARGET_HIT",
                exitPrice=ltp,
                reason=(
                    f"Target ₹{current_target:.2f} reached at ₹{ltp:.2f} with {micro['momentumState'].lower()} "
                    f"momentum ({micro['candleStructure']}, vol {micro['volumeRatio']}x); booking full profit"
                ),
                telemetry=telemetry,
            )

        # Runner Mode: Lock SL at the achieved target (or higher) and trail target upward
        locked_floor = round_tick(max(current_stop, current_target, ltp - max(0.20 * planned_move, micro["atr1m"])))
        # Ensure at least current_target is locked when crossing initial_target
        if current_target <= initial_target + 1e-6:
            locked_floor = round_tick(max(locked_floor, initial_target))
        if locked_floor > new_stop:
            new_stop = locked_floor
            reasons.append(f"locked SL at ₹{new_stop:.2f} on target breakout")

        step_up = max(0.30 * planned_move, 1.5 * float(micro["atr1m"]), 1.0)
        expanded_target = round_tick(max(current_target + TICK, ltp + step_up))
        if expanded_target > new_target:
            new_target = expanded_target
            reasons.append(
                f"trailed Target to ₹{new_target:.2f} ({micro['momentumState']} momentum, vol {micro['volumeRatio']}x)"
            )

    # 4. In-Trade Progressive Stop-Loss Ratchet (Before or After Initial Target)
    if trader_profile == "HIGH_CONVICTION":
        # High Win-Rate (e.g. 80-100%): Wait until 80% target achieved, then lock 50% of planned profit (e.g. 28 -> SL 25)
        if progress_pct >= 95.0:
            candidate_sl = round_tick(entry_at + 0.70 * planned_move)
            if candidate_sl > new_stop and candidate_sl < ltp:
                new_stop = candidate_sl
                reasons.append(f"95% target progress (peak ₹{peak:.2f}) → locked 70% profit SL at ₹{new_stop:.2f}")
        elif progress_pct >= 80.0:
            candidate_sl = round_tick(entry_at + 0.50 * planned_move)
            if candidate_sl > new_stop and candidate_sl < ltp:
                new_stop = candidate_sl
                reasons.append(
                    f"High-conviction 80% target achieved (peak ₹{peak:.2f}) → locked 50% profit SL at ₹{new_stop:.2f}"
                )
    else:
        # STEP_GUARD (~50% win-rate): Step 1 at 50% progress (25 -> SL 23), Step 2 at 80% progress (28 -> SL 25)
        if progress_pct >= 80.0:
            candidate_sl = round_tick(entry_at + 0.50 * planned_move)
            if candidate_sl > new_stop and candidate_sl < ltp:
                new_stop = candidate_sl
                reasons.append(
                    f"Step-guard 80% target progress (peak ₹{peak:.2f}) → trailed SL to ₹{new_stop:.2f} (+50% move locked)"
                )
        elif progress_pct >= 50.0:
            candidate_sl = round_tick(entry_at + 0.30 * planned_move)
            if candidate_sl > new_stop and candidate_sl < ltp:
                new_stop = candidate_sl
                reasons.append(
                    f"Step-guard 50% target progress (peak ₹{peak:.2f}) → trailed SL to ₹{new_stop:.2f} (above breakeven + costs)"
                )

    # 5. Beyond Initial Target (Runner Continuity between target expansions)
    if peak > initial_target and ltp > initial_target:
        # Keep SL ratcheted at least at initial_target and within 30% of total gain (or 1m support low)
        runner_sl = round_tick(max(initial_target, entry_at + 0.70 * (peak - entry_at)))
        if micro["supportLow"] and micro["supportLow"] > runner_sl and micro["supportLow"] < ltp:
            runner_sl = micro["supportLow"]
        if runner_sl > new_stop and runner_sl < ltp:
            new_stop = runner_sl
            reasons.append(f"runner trail above target (peak ₹{peak:.2f}) → raised SL to ₹{new_stop:.2f}")

    # 6. Live Microstructure / Climax Wick Tightening
    if (
        progress_pct >= 65.0
        and micro["candleStructure"] == "REJECTION_WICK"
        and micro["momentumState"] in ("FADING", "REVERSING")
    ):
        # If already past initial target and momentum reverses sharply, book runner immediately
        if peak >= initial_target and ltp >= initial_target:
            return BrainDecision(
                action="EXIT",
                newStop=new_stop,
                newTarget=new_target,
                exitReason="MOMENTUM_EXHAUSTED",
                exitPrice=ltp,
                reason=(
                    f"Runner momentum exhausted above target at ₹{ltp:.2f} "
                    f"(rejection wick {int(micro['upperWickRatio'] * 100)}%, vol {micro['volumeRatio']}x)"
                ),
                telemetry=telemetry,
            )
        # Otherwise tighten SL to protect 60% of the unrealized peak gain
        unrealized = max(0.0, peak - entry_at)
        tight_sl = round_tick(entry_at + 0.60 * unrealized)
        if tight_sl > new_stop and tight_sl < ltp:
            new_stop = tight_sl
            reasons.append(
                f"1m rejection wick with fading volume ({micro['volumeRatio']}x) → tightened SL to ₹{new_stop:.2f}"
            )
        # Also pull target closer if it hasn't been reached and momentum is fading
        if new_target > ltp + 0.25 * planned_move:
            pulled_target = round_tick(max(ltp + 0.15 * planned_move, peak))
            if pulled_target < new_target and pulled_target > entry_at:
                new_target = pulled_target
                reasons.append(f"pulled Target in to ₹{new_target:.2f} on fading volume")

    # Never allow stop to decrease
    new_stop = max(current_stop, new_stop)

    stop_changed = abs(new_stop - current_stop) >= 1e-4
    target_changed = abs(new_target - current_target) >= 1e-4
    if stop_changed and target_changed:
        action = "TRAIL_BOTH"
    elif stop_changed:
        action = "TRAIL_SL"
    elif target_changed:
        action = "TRAIL_TARGET"
    else:
        action = "HOLD"

    return BrainDecision(
        action=action,
        newStop=new_stop,
        newTarget=new_target,
        exitReason=None,
        exitPrice=None,
        reason="; ".join(reasons) if reasons else "Monitoring live premium & volume",
        telemetry=telemetry,
    )

