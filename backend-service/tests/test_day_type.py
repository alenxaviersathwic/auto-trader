"""Day type (noise area / PIN / RANGE / TREND / EXPANSION), the setups it gates, strike modes and premium exits."""
from datetime import datetime
from zoneinfo import ZoneInfo

from app.modules.opportunities.provider.underlying_config import get_config
from app.modules.opportunities.service import chain_recorder, day_type, menu_builder as mb, setups as su
from app.modules.opportunities.service.costs import slippage_pct

IST = ZoneInfo("Asia/Kolkata")


def _sessions(n, move):
    return [(f"2026-10-{i + 1:02d}", {0: {"o": 100.0, "c": 100.0}, 12: {"o": 100.0, "c": 100.0 * (1 + move)}}) for i in range(n)]


def test_noise_sigma_is_the_average_absolute_move_from_the_open():
    assert abs(day_type.noise_sigma(_sessions(14, -0.004), 12) - 0.004) < 1e-9
    assert day_type.noise_sigma(_sessions(day_type.MIN_NOISE_DAYS - 1, 0.004), 12) is None
    assert day_type.noise_proxy(300, 25000, 375, 375) == day_type.PROXY_ATR_SHARE * 300 / 25000


def test_noise_area_uses_the_open_and_the_previous_close():
    n = day_type.noise_area(25100, 25000, 0.004, 25250)
    assert n["upper"] == round(25100 * 1.004, 2) and n["lower"] == round(25000 * 0.996, 2) and n["state"] == "ABOVE"
    assert day_type.noise_area(25100, 25000, 0.004, 25050)["state"] == "INSIDE"
    assert day_type.round_levels(24873, 100) == (24800, 24900)


def _a(state, **kw):
    a = {"noise": {"state": state, "upper": 25150.0, "lower": 24900.0}, "levels": {"dayOpen": 25050, "pdc": 25030},
         "dailyAtr": 300, "spot": 25200, "session": {"minutesSinceOpen": 120}, "oi": {}}
    a.update(kw)
    return a


def test_day_type_rules():
    assert day_type.classify(_a("ABOVE"))["type"] == "TREND"
    exp = day_type.classify(_a("ABOVE", vix={"changePct": 4.0}))
    assert exp["type"] == "EXPANSION" and exp["side"] == "CE"
    assert day_type.classify(_a("BELOW", rangeUsedPct=90, spot=24800))["side"] == "PE"
    assert day_type.classify(_a("INSIDE", spot=25050))["type"] == "RANGE"
    pin = day_type.classify(_a("INSIDE", spot=25050, dte=0, expectedMovePct=0.6,
                               oi={"support": 25000, "resistance": 25100}, vix={"changePct": -1.0}))
    assert pin["type"] == "PIN"
    assert day_type.classify({})["type"] is None


def test_day_type_gates_setups_by_family():
    trend_ce = {"name": "VWAP_PULLBACK", "side": "CE"}
    reclaim = {"name": "FAILED_BREAK_RECLAIM", "side": "CE"}
    fade = {"name": "VWAP_BAND_REVERT", "side": "PE"}
    rng = {"dayType": {"type": "RANGE", "side": None}}
    tr = {"dayType": {"type": "TREND", "side": "PE"}}
    assert su.day_type_block(rng, trend_ce) and not su.day_type_block(rng, reclaim) and not su.day_type_block(rng, fade)
    assert su.day_type_block(tr, trend_ce) and su.day_type_block(tr, fade) and not su.day_type_block(tr, reclaim)
    assert not su.day_type_block(tr, {"name": "VWAP_PULLBACK", "side": "PE"})
    assert su.day_type_block({}, trend_ce) is None  # no noise area yet: no veto


def test_apply_bias_ignores_a_short_lived_opening_whipsaw():
    # BANKNIFTY 6 Nov 2026: a 14-minute opening dip read TREND/PE (565-579), then reverted to RANGE -- it must
    # NOT lock in as the day's bias (it never survived day_type.MIN_PERSIST_MIN = 15 minutes).
    state = {}
    for m in range(565, 580):
        state = day_type.apply_bias({"type": "TREND", "side": "PE"}, state, m)
    assert state["bias"] is None
    state = day_type.apply_bias({"type": "RANGE", "side": None}, state, 580)
    assert state["bias"] is None


def test_apply_bias_locks_in_a_direction_that_survives():
    state = {}
    for m in range(600, 616):  # 16 minutes >= MIN_PERSIST_MIN: this one sticks
        state = day_type.apply_bias({"type": "TREND", "side": "CE"}, state, m)
    assert state["bias"] == {"type": "TREND", "side": "CE", "rank": 2}
    # a pullback reading RANGE afterwards does not erase the established bias
    state = day_type.apply_bias({"type": "RANGE", "side": None}, state, 616)
    assert state["bias"]["side"] == "CE"
    # strengthening on the SAME side needs no fresh confirmation
    state = day_type.apply_bias({"type": "EXPANSION", "side": "CE"}, state, 617)
    assert state["bias"] == {"type": "EXPANSION", "side": "CE", "rank": 3}


def test_apply_bias_requires_persistence_to_flip_an_established_bias():
    state = {}
    for m in range(600, 616):
        state = day_type.apply_bias({"type": "TREND", "side": "CE"}, state, m)
    assert state["bias"]["side"] == "CE"
    state = day_type.apply_bias({"type": "TREND", "side": "PE"}, state, 616)  # one bar the other way: not enough
    assert state["bias"]["side"] == "CE"
    for m in range(616, 632):  # 16 minutes the other way: this flips it
        state = day_type.apply_bias({"type": "TREND", "side": "PE"}, state, m)
    assert state["bias"]["side"] == "PE"


def test_day_type_block_vetoes_against_a_confirmed_expansion_bias():
    reclaim_pe = {"name": "FAILED_BREAK_RECLAIM", "side": "PE"}
    a = {"dayType": {"type": "RANGE", "side": None}, "dayBias": {"type": "EXPANSION", "side": "CE", "rank": 3}}
    assert su.day_type_block(a, reclaim_pe)  # the sticky EXPANSION/CE bias vetoes a PE reversal bet
    assert not su.day_type_block(a, {"name": "FAILED_BREAK_RECLAIM", "side": "CE"})  # with the bias: fine


def _bars5(specs, start=555):
    return [{"t": "", "o": o, "h": h, "l": l, "c": c, "v": 1000, "oi": 0, "start": start + 5 * i, "done": True}
            for i, (o, h, l, c) in enumerate(specs)]


def test_noise_breakout_fires_on_the_first_close_outside():
    bars = _bars5([(100, 104, 99, 103), (103, 106, 102, 105), (105, 118, 104, 117)])
    a = {"bars5": bars, "atr5": 10.0, "regime": "MIXED", "trend15": "UP", "levels": {}, "keyLevels": [],
         "session": {"minutesSinceOpen": 40, "minutesToClose": 300},
         "noise": {"state": "ABOVE", "prevState": "INSIDE", "upper": 110.0, "lower": 90.0}}
    found = su.detect(a, None)
    nb = [s for s in found if s["name"] == "NOISE_BREAKOUT"]
    assert nb and nb[0]["side"] == "CE" and nb[0]["stop"] < 110
    a["noise"]["prevState"] = "ABOVE"  # not fresh
    assert not [s for s in su.detect(a, None) if s["name"] == "NOISE_BREAKOUT"]


def test_late_day_momentum_needs_both_halves_and_the_noise_side():
    bars = _bars5([(100, 104, 99, 103), (103, 106, 102, 105), (105, 112, 104, 111)])
    a = {"bars5": bars, "atr5": 10.0, "regime": "MIXED", "trend15": "UP", "levels": {"pdc": 100.0}, "keyLevels": [],
         "session": {"minutesSinceOpen": 320, "minutesToClose": 60}, "firstHalfHourRetPct": 0.4,
         "noise": {"state": "ABOVE", "prevState": "ABOVE", "upper": 108.0, "lower": 92.0}}
    assert [s for s in su.detect(a, None) if s["name"] == "LATE_DAY_MOMENTUM" and s["side"] == "CE"]
    a["firstHalfHourRetPct"] = -0.4
    assert not [s for s in su.detect(a, None) if s["name"] == "LATE_DAY_MOMENTUM"]


def test_strike_mode_table():
    trend = {"name": "NOISE_BREAKOUT", "family": "TREND"}
    reclaim = {"name": "FAILED_BREAK_RECLAIM", "family": "REVERSAL"}
    am, pm = datetime(2026, 11, 9, 10, 30, tzinfo=IST), datetime(2026, 11, 9, 14, 0, tzinfo=IST)
    exp0 = {"dayType": {"type": "EXPANSION"}, "dte": 0}
    assert mb.strike_mode(exp0, trend, am) == "OTM"
    assert mb.strike_mode(exp0, trend, pm) == "LOTTERY"
    assert mb.strike_mode({"dayType": {"type": "TREND"}, "dte": 0}, trend, pm) == "ITM"
    assert mb.strike_mode(exp0, reclaim, am) == "ATM"
    assert mb.strike_mode({"dayType": {"type": "RANGE"}, "dte": 0}, trend, am) == "ATM"
    assert mb.strike_mode({"dayType": {"type": "EXPANSION"}, "dte": 3}, trend, am) == "ATM"


def _leg(key, ltp, delta, spread):
    return {"key": key, "ltp": ltp, "oi": 50000, "volume": 5000, "bid": ltp - spread / 2, "ask": ltp + spread / 2,
            "delta": delta, "iv": 14}


def _market(spot=25000.0):
    rows = []
    for k in range(-8, 9):
        s = 25000 + 50 * k
        d = max(0.03, min(0.97, 0.5 - (s - spot) / 300))
        ce = max(1.0, 110 - (s - spot) * 0.5) if s <= spot else max(1.0, 110 * (d / 0.5) ** 2)
        pe = max(1.0, 110 + (s - spot) * 0.5) if s >= spot else max(1.0, 110 * ((1 - d) / 0.5) ** 2)
        rows.append({"strike": s, "CE": _leg(f"CE{s}", round(ce, 2), d, 0.05 if ce < 20 else 0.4),
                     "PE": _leg(f"PE{s}", round(pe, 2), -(1 - d), 0.05 if pe < 20 else 0.4)})
    return {"spot": spot, "chains": [{"expiry": "2026-11-09", "spot": spot, "strikes": rows, "resistance": None, "support": None}]}


def _setup(side="CE"):
    return {"name": "NOISE_BREAKOUT", "side": side, "strength": 4, "family": "TREND", "reason": "x",
            "entry": 25000, "stop": 24970, "target": 25090, "targetLevel": "2R"}


def test_otm_mode_picks_the_delta_band_with_premium_exits():
    cfg = get_config("NIFTY")
    menu = mb.build_menu(cfg, _market(), "BULLISH", 5.0, setups=[_setup()], require_setup=True, atm_itm_only=True,
                         min_delta=0.5, atr5=20.0, strike_modes={"CE": "OTM", "PE": "ATM"})
    assert menu and all(0.20 <= m["delta"] <= 0.35 and m["strike"] > 25000 for m in menu)
    m = menu[0]
    assert m["exitMode"] == "PREMIUM" and m["strikeMode"] == "OTM" and m["marginPct"] == 60.0
    assert mb.OTM_MIN_STOP_PCT <= m["stopPct"] <= 35.0 and m["timeStopMin"] == 10
    assert abs(m["riskPerLot"] - (m["entry"] - m["stop"]) * 65) <= 1


def test_lottery_mode_risks_the_whole_premium_and_skips_sub_2_rupee_options():
    cfg = get_config("NIFTY")
    reasons: dict = {}
    menu = mb.build_menu(cfg, _market(), "BULLISH", 5.0, setups=[_setup()], require_setup=True, atm_itm_only=True,
                         atr5=20.0, strike_modes={"CE": "LOTTERY", "PE": "ATM"}, reasons=reasons)
    assert menu and all(0.08 <= m["delta"] <= 0.20 and m["entry"] >= mb.MIN_PREMIUM for m in menu)
    m = menu[0]
    assert m["stopPct"] == 50.0 and m["marginPct"] == 100.0 and abs(m["riskPerLot"] - m["entry"] * 65) <= 1
    assert any(k.startswith("premium<Rs") for k in reasons)


def test_cheap_options_use_the_one_tick_spread_rule():
    cfg = get_config("NIFTY")
    mk = _market()
    for r in mk["chains"][0]["strikes"]:
        if r["CE"]["ltp"] < 20:
            r["CE"]["bid"], r["CE"]["ask"] = r["CE"]["ltp"] - 0.1, r["CE"]["ltp"] + 0.1  # 4 ticks wide
    reasons: dict = {}
    menu = mb.build_menu(cfg, mk, "BULLISH", 5.0, setups=[_setup()], require_setup=True, atr5=20.0,
                         strike_modes={"CE": "LOTTERY", "PE": "ATM"}, reasons=reasons)
    assert not [m for m in menu if m["entry"] < 20] and reasons.get("spread>1 tick", 0) >= 1


def test_atm_mode_keeps_the_point_exits():
    cfg = get_config("NIFTY")
    menu = mb.build_menu(cfg, _market(), "BULLISH", 1.0, setups=[_setup()], require_setup=True, atm_itm_only=True,
                         atr5=20.0, strike_modes={"CE": "ATM", "PE": "ATM"})
    assert menu and all(m["exitMode"] == "POINTS" and m["delta"] >= 0.45 and m["strike"] <= 25000 for m in menu)


def test_slippage_is_a_tick_per_side_on_cheap_options():
    assert slippage_pct(2.0) == 5.0 and slippage_pct(100.0) == 0.5 and slippage_pct(0) == 0.0


def test_chain_recorder_packs_rows_and_throttles():
    rows = chain_recorder.pack(_market()["chains"][0])
    assert len(rows) == 17 and len(rows[0]) == 15 and rows[0][0] == 24600
    chain_recorder._last["X"] = 100.0
    assert not chain_recorder.due("X", 120.0) and chain_recorder.due("X", 160.0) and chain_recorder.due("NEW", 0.0)
