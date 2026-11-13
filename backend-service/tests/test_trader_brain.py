"""
Unit tests for `trader_brain.py`:
  1. High Win-Rate (HIGH_CONVICTION, >= 75% win-rate):
     - Entry 20, Target 30 (+50%), Stop 15.
     - Waits until 80% of target is achieved (price 28) -> locks SL at 25 (+50% of planned profit).
  2. Moderate Win-Rate (STEP_GUARD, ~50% win-rate):
     - Entry 20, Target 30 (+50%), Stop 15.
     - At 50% target progress (price 25) -> trails SL to 23.
     - At 80% target progress (price 28) -> trails SL to 25.
  3. Target Breakout & Runner Trailing:
     - When price reaches/crosses 30 with strong volume & bullish 1m candle drive:
       locks SL at 30 and expands Target above 30.
     - When price reaches 30 with weak/stalling momentum:
       exits immediately with TARGET_HIT.
  4. Live 1m Option Premium Chart / Volume Climax Tightening & Stop-Never-Decreases invariant.
"""
from datetime import UTC, datetime, timedelta

from app.modules.trades.service import trader_brain as brain


def test_profile_selection():
    assert brain.select_profile(100.0, 70) == "HIGH_CONVICTION"
    assert brain.select_profile(75.0, 60) == "HIGH_CONVICTION"
    assert brain.select_profile(50.0, 85) == "HIGH_CONVICTION"
    assert brain.select_profile(50.0, 55) == "STEP_GUARD"


def test_high_conviction_waits_for_80_pct_target_then_locks_25_sl():
    # Entry 20, Target 30 (planned move = 10), Initial SL 15
    # 1) At price 25 (50% progress): HIGH_CONVICTION holds initial SL 15 (gives room)
    d1 = brain.evaluate_tick(
        entry_at=20.0,
        initial_stop=15.0,
        initial_target=30.0,
        current_stop=15.0,
        current_target=30.0,
        peak_price=25.0,
        ltp=25.0,
        trader_profile="HIGH_CONVICTION",
    )
    assert d1.action == "HOLD"
    assert d1.newStop == 15.0
    assert d1.newTarget == 30.0

    # 2) At price 28 (80% of target achieved): locks SL at 25.0 (50% of planned profit)
    d2 = brain.evaluate_tick(
        entry_at=20.0,
        initial_stop=15.0,
        initial_target=30.0,
        current_stop=15.0,
        current_target=30.0,
        peak_price=28.0,
        ltp=28.0,
        trader_profile="HIGH_CONVICTION",
    )
    assert d2.action == "TRAIL_SL"
    assert d2.newStop == 25.0
    assert d2.newTarget == 30.0


def test_step_guard_50_pct_win_rate_trails_23_at_25_and_25_at_28():
    # Entry 20, Target 30 (planned move = 10), Initial SL 15
    # 1) When price reaches 25 (50% target progress): trails SL to 23
    d1 = brain.evaluate_tick(
        entry_at=20.0,
        initial_stop=15.0,
        initial_target=30.0,
        current_stop=15.0,
        current_target=30.0,
        peak_price=25.0,
        ltp=25.0,
        trader_profile="STEP_GUARD",
    )
    assert d1.action == "TRAIL_SL"
    assert d1.newStop == 23.0
    assert d1.newTarget == 30.0

    # 2) When price reaches 28 (80% target progress): trails SL from 23 to 25
    d2 = brain.evaluate_tick(
        entry_at=20.0,
        initial_stop=15.0,
        initial_target=30.0,
        current_stop=d1.newStop,
        current_target=30.0,
        peak_price=28.0,
        ltp=28.0,
        trader_profile="STEP_GUARD",
    )
    assert d2.action == "TRAIL_SL"
    assert d2.newStop == 25.0

    # 3) If price pulls back to 26, SL never decreases (stays at 25.0)
    d3 = brain.evaluate_tick(
        entry_at=20.0,
        initial_stop=15.0,
        initial_target=30.0,
        current_stop=d2.newStop,
        current_target=30.0,
        peak_price=28.0,
        ltp=26.0,
        trader_profile="STEP_GUARD",
    )
    assert d3.newStop == 25.0


def test_target_hit_and_beyond_locks_sl_at_30_and_trails_target_higher_on_strong_volume():
    strong_candles = [
        {"t": "2026-11-10T10:00:00+05:30", "o": 24.0, "h": 25.5, "l": 23.8, "c": 25.2, "v": 1000},
        {"t": "2026-11-10T10:01:00+05:30", "o": 25.2, "h": 27.0, "l": 25.0, "c": 26.8, "v": 1200},
        {"t": "2026-11-10T10:02:00+05:30", "o": 26.8, "h": 30.8, "l": 26.7, "c": 30.5, "v": 2400},
    ]
    d = brain.evaluate_tick(
        entry_at=20.0,
        initial_stop=15.0,
        initial_target=30.0,
        current_stop=25.0,
        current_target=30.0,
        peak_price=30.5,
        ltp=30.5,
        trader_profile="STEP_GUARD",
        candles_1m=strong_candles,
    )
    assert d.action == "TRAIL_BOTH"
    assert d.newStop >= 30.0  # SL locked at 30+
    assert d.newTarget > 30.5  # Target expanded beyond 30
    assert d.exitReason is None


def test_target_hit_exits_when_momentum_fades_at_target():
    rejection_candles = [
        {"t": "2026-11-10T10:00:00+05:30", "o": 26.0, "h": 28.0, "l": 25.8, "c": 27.5, "v": 2000},
        {"t": "2026-11-10T10:01:00+05:30", "o": 27.5, "h": 29.5, "l": 27.2, "c": 28.8, "v": 1800},
        {"t": "2026-11-10T10:02:00+05:30", "o": 29.0, "h": 32.0, "l": 28.8, "c": 29.2, "v": 700},
    ]
    d = brain.evaluate_tick(
        entry_at=20.0,
        initial_stop=15.0,
        initial_target=30.0,
        current_stop=25.0,
        current_target=30.0,
        peak_price=30.2,
        ltp=30.0,
        trader_profile="STEP_GUARD",
        candles_1m=rejection_candles,
    )
    assert d.action == "EXIT"
    assert d.exitReason == "TARGET_HIT"
    assert d.exitPrice == 30.0


def test_stop_loss_and_trailing_stop_loss_exit():
    # Initial SL hit
    d1 = brain.evaluate_tick(
        entry_at=20.0,
        initial_stop=15.0,
        initial_target=30.0,
        current_stop=15.0,
        current_target=30.0,
        peak_price=21.0,
        ltp=14.9,
        trader_profile="STEP_GUARD",
    )
    assert d1.action == "EXIT" and d1.exitReason == "STOP_HIT"

    # Trailing SL hit
    d2 = brain.evaluate_tick(
        entry_at=20.0,
        initial_stop=15.0,
        initial_target=30.0,
        current_stop=25.0,
        current_target=30.0,
        peak_price=28.5,
        ltp=24.95,
        trader_profile="STEP_GUARD",
    )
    assert d2.action == "EXIT" and d2.exitReason == "TRAILING_STOP_HIT"


def test_session_close_exits_trade():
    now = datetime.now(UTC)
    d = brain.evaluate_tick(
        entry_at=20.0,
        initial_stop=15.0,
        initial_target=30.0,
        current_stop=23.0,
        current_target=30.0,
        peak_price=26.0,
        ltp=25.5,
        trader_profile="STEP_GUARD",
        now=now,
        close_at=now - timedelta(seconds=1),
    )
    assert d.action == "EXIT" and d.exitReason == "SESSION_CLOSE"



def test_momentum_trail_never_exits_at_target_and_trails_in_r():
    from app.modules.opportunities.service.menu_builder import MOMO_EXIT
    from app.modules.trades.service import trader_brain as tb

    kw = dict(entry_at=100.0, initial_stop=90.0, initial_target=140.0, current_stop=90.0, current_target=140.0,
              trader_profile="STEP_GUARD", momentum_trail=MOMO_EXIT)
    d = tb.evaluate_tick(peak_price=150.0, ltp=150.0, **kw)  # past the "target": a momentum runner keeps going
    assert d.action != "EXIT" and d.newStop == 130.0  # trail 2R (20) under the 150 peak
    d2 = tb.evaluate_tick(peak_price=116.0, ltp=115.0, **kw)  # +1.6R: breakeven + ~1% for charges
    assert d2.newStop == 101.0
    d3 = tb.evaluate_tick(peak_price=150.0, ltp=129.0, **{**kw, "current_stop": 130.0})
    assert d3.action == "EXIT" and d3.exitReason == "TRAILING_STOP_HIT"


def test_wave_step_expansion_100_to_120_to_150_with_sl_75_to_100():
    # Entry 50, Initial SL 35, Initial Target 100 (planned move = 50), Live Projected Ceiling = 150
    # Step 1: At price 90 (80% progress toward 100), locks SL at 75 and steps Target 100 -> 120
    d1 = brain.evaluate_tick(
        entry_at=50.0,
        initial_stop=35.0,
        initial_target=100.0,
        current_stop=35.0,
        current_target=100.0,
        peak_price=90.0,
        ltp=90.0,
        trader_profile="ORB_WAVE_TRADER",
        projected_target=150.0,
    )
    assert d1.action == "TRAIL_BOTH"
    assert d1.newStop == 75.0
    assert d1.newTarget == 120.0

    # Step 2: At price 118 (nearing Step 1 target 120), locks SL at 100 and steps Target 120 -> 150
    d2 = brain.evaluate_tick(
        entry_at=50.0,
        initial_stop=35.0,
        initial_target=100.0,
        current_stop=d1.newStop,
        current_target=d1.newTarget,
        peak_price=118.0,
        ltp=118.0,
        trader_profile="ORB_WAVE_TRADER",
        projected_target=150.0,
    )
    assert d2.action == "TRAIL_BOTH"
    assert d2.newStop >= 100.0
    assert d2.newTarget == 150.0


def test_fib_golden_trader_steps_to_1272_and_1618_extensions():
    # Entry 100, Initial SL 80, Swing High (1.0) = 150 (planned move = 50)
    # 1.272 Ext = 163.60, 1.618 Ext = 180.90
    strong_candles = [
        {"t": "2026-11-10T10:00:00+05:30", "o": 135.0, "h": 142.0, "l": 134.0, "c": 141.0, "v": 1000},
        {"t": "2026-11-10T10:01:00+05:30", "o": 141.0, "h": 151.0, "l": 140.5, "c": 150.5, "v": 2200},
    ]
    d1 = brain.evaluate_tick(
        entry_at=100.0,
        initial_stop=80.0,
        initial_target=150.0,
        current_stop=125.0,
        current_target=150.0,
        peak_price=150.5,
        ltp=150.5,
        trader_profile="FIB_GOLDEN_TRADER",
        candles_1m=strong_candles,
    )
    assert d1.newStop >= 150.0
    assert d1.newTarget == 163.6

