"""Two traders (Fib Golden-Pocket / Flow & Momentum), the Fib setup's OI + volume confirmations, the session
risk level and the real option-chain (OI) view. Pure functions only: no DB, no network."""

from datetime import UTC, datetime

from app.modules.opportunities.service import chain_view, fib_pocket
from app.modules.opportunities.service import setups as setup_detector
from app.modules.sessions.service import session_risk as sr
from app.modules.trades.service import trader_brain as brain
from app.modules.trades.service import trader_presets as tp

ATR = 10.0
TICK = 1.0


def _bars(specs, vols=None):
    """specs: (o, h, l, c) 5-minute bars; returns (spot bars, futures bars with the given volumes)."""
    vols = vols or [1000] * len(specs)
    spot = [{"t": f"T{i:02d}", "o": o, "h": h, "l": l, "c": c, "v": 0} for i, (o, h, l, c) in enumerate(specs)]
    fut = [{**b, "v": v} for b, v in zip(spot, vols, strict=True)]
    return spot, fut


# Swing 99 -> 141 (4.2 ATR), pullback low 116.6 (0.58 retracement), turn bar closes 119.2 (green, above prev close)
CE_SPECS = [(100, 101, 99, 100), (100, 102, 99.5, 101), (101, 115, 100, 114), (114, 130, 113, 129),
            (129, 141, 128, 140), (140, 140.5, 126, 127), (127, 128, 117, 118), (118, 119.5, 116.6, 119.2)]
CE_VOLS = [800, 800, 2000, 2200, 2100, 900, 800, 1300]


def _ce_analysis(**over):
    spot, fut = _bars(CE_SPECS, CE_VOLS)
    a = {"bars5": spot, "futBars5": fut, "atr5": ATR, "volume": {"ratio5m": 1.3},
         "oi": {"support": 110.0, "resistance": 150.0, "pcr": 1.1}, "buildup": {"state": "NEUTRAL"}}
    a.update(over)
    return a


def test_fib_pocket_ce_fires_with_oi_and_volume_confirmation():
    a = _ce_analysis()
    out = fib_pocket.detect(a, a["bars5"], ATR, TICK)
    assert len(out) == 1
    s = out[0]
    assert (s["name"], s["side"]) == ("FIB_GOLDEN_POCKET", "CE")
    assert s["confirmBlock"] is None and s["oiConfirmed"] and s["volumeConfirmed"]
    assert s["entry"] == 119.2 and s["target"] == 141  # target = the swing high (Fib 1.0)
    assert s["stop"] == round(141 - 0.786 * 42 - TICK, 2)  # just beyond the 0.786 retracement
    assert s["rr"] >= fib_pocket.MIN_RR
    assert s["fib"]["swingLow"] == 99 and s["fib"]["swingHigh"] == 141
    assert s["fib"]["fib1618"] == round(99 + 1.618 * 42, 2)


def test_fib_pocket_blocked_by_call_oi_wall_in_the_path():
    a = _ce_analysis(oi={"support": 110.0, "resistance": 125.0, "pcr": 0.8})
    s = fib_pocket.detect(a, a["bars5"], ATR, TICK)[0]
    assert not s["oiConfirmed"] and "call-OI wall 125" in s["confirmBlock"]
    assert setup_detector.policy_block({"code": "NIFTY"}, s) == s["confirmBlock"]


def test_fib_pocket_needs_oi_backing_or_agreeing_flow():
    a = _ce_analysis(oi={"support": 60.0, "resistance": 150.0})  # put wall far below, futures neutral
    assert not fib_pocket.detect(a, a["bars5"], ATR, TICK)[0]["oiConfirmed"]
    a = _ce_analysis(oi={"support": 60.0, "resistance": 150.0}, buildup={"state": "LONG_BUILDUP"})
    assert fib_pocket.detect(a, a["bars5"], ATR, TICK)[0]["oiConfirmed"]
    a = _ce_analysis(oi={})  # no chain at all: never confirmed
    assert "no option-chain OI data" in fib_pocket.detect(a, a["bars5"], ATR, TICK)[0]["confirmBlock"]


def test_fib_pocket_blocked_by_volume():
    a = _ce_analysis(volume={"ratio5m": 0.6})  # nobody traded the turn bar
    s = fib_pocket.detect(a, a["bars5"], ATR, TICK)[0]
    assert not s["volumeConfirmed"] and "turn bar volume" in s["confirmBlock"]
    spot, fut = _bars(CE_SPECS, [800, 800, 1000, 1000, 1000, 2500, 2600, 1300])  # heavy selling in the pullback
    a = _ce_analysis(bars5=spot, futBars5=fut)
    s = fib_pocket.detect(a, a["bars5"], ATR, TICK)[0]
    assert not s["volumeConfirmed"] and "pullback volume" in s["confirmBlock"]


def test_fib_pocket_rejects_small_swing_deep_pullback_and_no_turn():
    a = _ce_analysis()
    assert fib_pocket.detect(a, a["bars5"], 20.0, 2.0) == []  # 42 pts is only 2.1 ATR: not an impulse
    deep = CE_SPECS[:-2] + [(127, 128, 107, 108), (108, 112, 107.5, 111)]  # 0.81 retracement: pocket failed
    spot, fut = _bars(deep, CE_VOLS)
    assert fib_pocket.detect(_ce_analysis(bars5=spot, futBars5=fut), spot, ATR, TICK) == []
    red = CE_SPECS[:-1] + [(118, 118.5, 116.6, 117)]  # still falling: no turn bar yet
    spot, fut = _bars(red, CE_VOLS)
    assert fib_pocket.detect(_ce_analysis(bars5=spot, futBars5=fut), spot, ATR, TICK) == []


def test_fib_pocket_pe_is_the_mirror():
    specs = [(o and 240 - o, 240 - l, 240 - h, 240 - c) for (o, h, l, c) in CE_SPECS]
    spot, fut = _bars(specs, CE_VOLS)
    a = {"bars5": spot, "futBars5": fut, "atr5": ATR, "volume": {"ratio5m": 1.3},
         "oi": {"support": 90.0, "resistance": 130.0}, "buildup": {"state": "NEUTRAL"}}
    s = fib_pocket.detect(a, spot, ATR, TICK)[0]
    assert s["side"] == "PE" and s["confirmBlock"] is None
    assert s["target"] == 99 and s["stop"] > s["entry"] > s["target"]


def test_fib_setup_is_wired_into_detect_and_policy():
    a = {**_ce_analysis(), "regime": "MIXED", "trend15": "UP", "levels": {}, "keyLevels": [],
         "session": {"minutesSinceOpen": 120}}
    names = [s["name"] for s in setup_detector.detect(a, None)]
    assert "FIB_GOLDEN_POCKET" in names
    assert setup_detector.SETUP_POLICY["FIB_GOLDEN_POCKET"] == "CONFIRMED"
    assert setup_detector.family("FIB_GOLDEN_POCKET") == "TREND"


# ───────────────────────── traders ─────────────────────────
def test_only_two_traders_and_old_codes_map():
    assert tp.ALL_PRESET_TRADER_CODES == ("FIB_GOLDEN_TRADER", "FLOW_MOMENTUM_TRADER")
    assert [p["code"] for p in tp.TRADER_PRESETS] == list(tp.ALL_PRESET_TRADER_CODES)
    assert tp.normalize_trader_code("ORB_WAVE_TRADER") == "FLOW_MOMENTUM_TRADER"
    assert tp.normalize_trader_code("FLOW_VWAP_TRADER") == "FLOW_MOMENTUM_TRADER"
    assert tp.normalize_trader_code("STEP_GUARD") is None
    assert tp.normalize_trader_codes(["FIB_GOLDEN_TRADER", "ORB_WAVE_TRADER", "FLOW_VWAP_TRADER"]) == [
        "FIB_GOLDEN_TRADER", "FLOW_MOMENTUM_TRADER"]
    assert tp.normalize_trader_codes(["FLOW_VWAP_TRADER"]) == ["FLOW_MOMENTUM_TRADER"]
    assert tp.normalize_trader_codes([]) == list(tp.ALL_PRESET_TRADER_CODES)
    assert tp.get_trader_preset("ORB_WAVE_TRADER")["code"] == "FLOW_MOMENTUM_TRADER"


def test_trader_ownership_is_by_setup_not_confidence():
    assert tp.assign_trader_for_opportunity("FIB_GOLDEN_POCKET") == "FIB_GOLDEN_TRADER"
    assert tp.assign_trader_for_opportunity("Fibonacci Golden Pocket") == "FIB_GOLDEN_TRADER"
    for other in ("NOISE_BREAKOUT", "INSIDE_BAR", "VWAP_PULLBACK", "baseline-rr", None, "EMA_CROSS_RETEST"):
        assert tp.assign_trader_for_opportunity(other, 95, 3.0) == "FLOW_MOMENTUM_TRADER"


def _tick(code, ltp, peak, **kw):
    return brain.evaluate_tick(entry_at=100, initial_stop=85, initial_target=130, current_stop=85,
                               current_target=130, peak_price=peak, ltp=ltp, trader_profile="STEP_GUARD",
                               trader_code=code, **kw)


def test_the_two_traders_manage_the_same_trade_differently():
    # 60% of the way to target: the Flow trader already protects (+30% of the move), the Fib trader still waits
    flow = _tick("FLOW_MOMENTUM_TRADER", 118, 118)
    fib = _tick("FIB_GOLDEN_TRADER", 118, 118)
    assert flow.action == "TRAIL_SL" and flow.newStop == 109.0
    assert fib.action == "HOLD" and fib.newStop == 85
    # 85%: the Fib trader locks half the move
    assert _tick("FIB_GOLDEN_TRADER", 125.5, 125.5).newStop == 115.0
    # old three-trader codes stored on running trades keep working
    assert _tick("ORB_WAVE_TRADER", 118, 118).newStop == flow.newStop


# ───────────────────────── session risk level ─────────────────────────
def test_risk_level_default_and_profiles():
    assert sr.DEFAULT_RISK_LEVEL == "LOW"
    assert sr.normalize_risk_level(None) == "LOW" and sr.normalize_risk_level("medium") == "MEDIUM"
    assert sr.normalize_risk_level("nonsense") == "LOW"
    assert sr.profile_for("HIGH").policies is None


def test_low_takes_only_proven_setups_with_trend():
    assert sr.risk_gate("LOW", "NOISE_BREAKOUT", 2.0, []) is None
    assert sr.risk_gate("LOW", "FIB_GOLDEN_POCKET", 1.6, []) is None
    assert "not a proven setup" in sr.risk_gate("LOW", "VWAP_PULLBACK", 2.5, [])  # MERGED
    assert "not a proven setup" in sr.risk_gate("LOW", "baseline-rr", 2.5, [])
    assert "reward:risk below 1.5" in sr.risk_gate("LOW", "NOISE_BREAKOUT", 1.4, [])
    assert "against the trend" in sr.risk_gate("LOW", "NOISE_BREAKOUT", 2.0, ["Against the bullish trend"])


def test_medium_and_high_widen_what_is_accepted():
    assert sr.risk_gate("MEDIUM", "VWAP_PULLBACK", 1.35, []) is None
    assert "not a coded setup" in sr.risk_gate("MEDIUM", "baseline-rr", 3.0, [])
    assert "against the trend" in sr.risk_gate("MEDIUM", "INSIDE_BAR", 2.0, ["Against the bearish trend"])
    assert sr.risk_gate("HIGH", "baseline-rr", 1.2, ["Against the bearish trend"]) is None
    assert sr.risk_gate("HIGH", None, 0.0, None) is None


# ───────────────────────── real option-chain view ─────────────────────────
def _row(strike, ce_oi, pe_oi, ce_vol=100, pe_vol=100):
    return [strike, 10, ce_oi, ce_vol, 9, 11, 0.5, 14, 10, pe_oi, pe_vol, 9, 11, -0.5, 14]


def test_chain_view_uses_only_recorded_numbers():
    at = datetime(2026, 11, 16, 5, 0, tzinfo=UTC)
    cur = {"spot": 24510, "pcr": 1.2, "at": at, "strikes": [
        _row(24400, 1000, 9000), _row(24450, 2000, 6000), _row(24500, 3000, 5000, 400, 400),
        _row(24550, 5000, 2000), _row(24600, 8000, 1000)]}
    prev = {"spot": 24480, "pcr": 1.1, "at": at, "strikes": [
        _row(24400, 1000, 6000), _row(24450, 2000, 6000), _row(24500, 3000, 4000),
        _row(24550, 5000, 2000), _row(24600, 8000, 1000)]}
    v = chain_view.build(24500, "CE", cur, prev)
    assert v["source"] == "CHAIN_SNAPSHOT" and v["asOf"] == at.isoformat()
    assert v["putOiSupportWall"] == 24400 and v["callOiResistanceWall"] == 24600
    active = next(r for r in v["strikes"] if r["role"] == "ACTIVE_STRIKE")
    assert (active["strike"], active["callOi"], active["putOi"], active["putOiChgPct"]) == (24500, 3000, 5000, 25.0)
    assert v["oiBuildup"] == "PUT_WRITING" and "supports this CE" in v["verdict"]
    assert v["maxPain"] in (24450, 24500, 24550)
    # no earlier snapshot: change is unknown, never invented
    v2 = chain_view.build(24500, "PE", cur, None)
    assert v2["oiBuildup"] == "NO_HISTORY" and all(r["putOiChgPct"] is None for r in v2["strikes"])
    assert chain_view.build(24500, "CE", {"spot": 0, "strikes": [], "at": at}, None) is None


# ───────────────────────── real swing carried to the trade ─────────────────────────
def test_setup_meta_turns_the_real_swing_into_premium_levels():
    a = _ce_analysis()
    s = fib_pocket.detect(a, a["bars5"], ATR, TICK)[0]
    m = fib_pocket.setup_meta(s, spot=119.2, ltp=50.0, delta=0.5)
    assert m["kind"] == "FIB_GOLDEN_POCKET" and m["underlying"]["swingLow"] == 99 and m["underlying"]["swingHigh"] == 141
    assert m["premium"]["fib100"] == round(50 + 0.5 * (141 - 119.2), 2)           # swing high in premium terms
    assert m["premium"]["fib1272"] == round(50 + 0.5 * (99 + 1.272 * 42 - 119.2), 2)
    assert m["premium"]["fib786"] < 50 < m["premium"]["fib100"] < m["premium"]["fib1272"] < m["premium"]["fib1618"]
    assert fib_pocket.setup_meta({"name": "NOISE_BREAKOUT", "side": "CE"}, 100, 50, 0.5) is None


def test_trade_levels_come_from_the_swing_or_are_labelled_plan():
    from app.modules.trades.service.trade_service import _fib_levels, _real_extensions

    a = _ce_analysis()
    meta = fib_pocket.setup_meta(fib_pocket.detect(a, a["bars5"], ATR, TICK)[0], 119.2, 50.0, 0.5)
    real = _fib_levels(52.0, 44.0, 60.0, meta)  # filled 2.00 above the premium at signal: every level shifts by 2
    assert real["source"] == "SETUP_SWING" and real["underlying"]["swingHigh"] == 141
    assert real["fib100"] == brain.round_tick(meta["premium"]["fib100"] + 2.0)
    assert _real_extensions(real) == (real["fib1272"], real["fib1618"])
    plan = _fib_levels(52.0, 44.0, 60.0, None)
    assert plan["source"] == "PLAN" and "swingLow" not in plan and "swingHigh" not in plan  # nothing invented
    assert plan["fib1272"] == brain.round_tick(52 + 1.272 * 8) and _real_extensions(plan) is None


def test_fib_trader_steps_to_the_real_swing_extensions():
    kw = dict(entry_at=100, initial_stop=85, initial_target=130, current_stop=85, current_target=130,
              peak_price=131, ltp=131, trader_profile="STEP_GUARD", trader_code="FIB_GOLDEN_TRADER",
              candles_1m=[{"t": "", "o": 120 + i, "h": 122 + i, "l": 119.5 + i, "c": 121.8 + i, "v": 100 + 40 * i}
                          for i in range(8)])
    plain = brain.evaluate_tick(**kw)
    real = brain.evaluate_tick(**kw, fib_extensions=(150.0, 171.0))
    assert plain.newTarget == brain.round_tick(100 + 1.272 * 30)  # 1.272x of the planned move
    assert real.newTarget == 150.0 and real.telemetry["fibLevels"]["fib1618"] == 171.0
    # a real extension below the first target is never used as a target
    assert brain.evaluate_tick(**kw, fib_extensions=(120.0, 125.0)).newTarget > 130
