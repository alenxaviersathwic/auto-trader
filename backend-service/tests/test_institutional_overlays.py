from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.modules.opportunities.service import event_calendar, gamma_regime as gr, positioning as pos
from app.modules.opportunities.service import setups as su

IST = ZoneInfo("Asia/Kolkata")

SAMPLE = """Participant wise Open Interest (no. of contracts) in Equity Derivatives as on Nov 09, 2026
Client Type,Future Index Long,Future Index Short,Future Stock Long,Future Stock Short\t,Option Index Call Long,Option Index Put Long,Option Index Call Short,Option Index Put Short,Option Stock Call Long,Option Stock Put Long,Option Stock Call Short,Option Stock Put Short,Total Long Contracts\t,Total Short Contracts
Client,300000,150000,1,1,900000,800000,700000,600000,1,1,1,1,1,1
DII,10,20,1,1,0,0,0,0,1,1,1,1,1,1
FII,33124,90741,1,1,100,200,300,400,1,1,1,1,1,1
Pro,5,5,1,1,1,1,1,1,1,1,1,1,1,1
TOTAL,1,1,1,1,1,1,1,1,1,1,1,1,1,1
"""


def test_participant_oi_parse_and_ratio():
    p = pos.parse(SAMPLE)
    assert p["FII"]["futLong"] == 33124 and p["FII"]["futShort"] == 90741 and p["CLIENT"]["callLong"] == 900000
    assert abs(pos.fii_long_ratio(p) - 33124 / (33124 + 90741)) < 1e-4


def test_positioning_bias_rules():
    assert pos.bias([0.2] * 4) == 0  # too little history
    assert pos.bias([0.20, 0.22, 0.24, 0.26, 0.28, 0.30]) == 1
    assert pos.bias([0.16, 0.15, 0.14, 0.13, 0.12, 0.11]) == -1
    assert pos.bias([0.2] * 6, fii_net=[-5.0, 3.0]) == 1  # flip to net long


def test_gamma_signs_regime_and_route():
    assert gr.participant_signs(None) == (1, -1)
    assert gr.participant_signs({"callLong": 9, "callShort": 7, "putLong": 8, "putShort": 6}) == (-1, -1)
    hist = [float(i) for i in range(60)]
    assert gr.regime(59.0, hist) == "POSITIVE" and gr.regime(0.0, hist) == "NEGATIVE" and gr.regime(30.0, hist) == "NEUTRAL"
    assert gr.regime(1.0, hist[:10]) is None
    assert gr.route("POSITIVE")["momentumShort"] is False and gr.route("NEGATIVE")["shortPremium"] is False
    assert all(gr.route(None).values())


def test_net_gex_sign_follows_convention():
    chain = {"expiry": "2026-11-17", "strikes": [{"strike": 25000.0, "CE": {"iv": 14.0, "oi": 1e6}, "PE": {"iv": 14.0, "oi": 1e5}}]}
    now = datetime(2026, 11, 17, 10, 0, tzinfo=IST)
    assert gr.net_gex(chain, 25000.0, now) > 0  # call-heavy OI, dealers long calls (default convention)
    assert gr.net_gex(chain, 25000.0, now, call_sign=-1, put_sign=1) < 0
    assert gr.bs_gamma(25000, 25000, 14, 0.01) > gr.bs_gamma(25000, 26000, 14, 0.01)


def test_gamma_router_blocks_momentum_shorts_only_when_enabled():
    s = {"name": "NOISE_BREAKOUT", "side": "PE"}
    a = {"gamma": {"enabled": True, "regime": "POSITIVE", "route": gr.route("POSITIVE")}}
    assert "momentum shorts blocked" in su.policy_block(a, s)
    assert su.policy_block({**a, "gamma": {**a["gamma"], "enabled": False}}, s) is None
    assert su.policy_block(a, {**s, "side": "CE"}) is None


def test_event_calendar_tags():
    assert event_calendar.event_tags(date(2026, 12, 4)) == ["EVENT_RBI_MPC"]
    assert "EVENT_FOMC_OVERNIGHT" in event_calendar.event_tags(date(2026, 12, 10))
    assert event_calendar.event_tags(date(2026, 11, 11)) == []


def test_v2_rules_trend_vwap_pullback_and_entry_window():
    from app.modules.opportunities.service import institutional_filters as inst

    on = inst.enabled("TREND_5_20,NO_VWAP_PULLBACK,ENTRY_10_1430")
    bar = lambda hhmm: [{"t": f"2026-11-12T{hhmm}:00+05:30", "c": 100.0}]  # noqa: E731
    up = {"trendDays": {5: "UP", 20: "UP"}, "bars1": bar("10:30")}
    assert inst.block(up, {"name": "NOISE_BREAKOUT", "side": "CE"}, "NIFTY", on) is None
    assert "TREND_5_20" in inst.block(up, {"name": "NOISE_BREAKOUT", "side": "PE"}, "NIFTY", on)
    mixed = {"trendDays": {5: "UP", 20: "DOWN"}, "bars1": bar("10:30")}
    assert inst.block(mixed, {"name": "RANGE_BREAKOUT", "side": "CE"}, "BANKNIFTY", on)
    assert "NO_VWAP_PULLBACK" in inst.block(up, {"name": "VWAP_PULLBACK", "side": "CE"}, "NIFTY", on)
    assert "ENTRY_10_1430" in inst.block({**up, "bars1": bar("09:40")}, {"name": "NOISE_BREAKOUT", "side": "CE"}, "NIFTY", on)
    assert "ENTRY_10_1430" in inst.block({**up, "bars1": bar("14:45")}, {"name": "LATE_DAY_MOMENTUM", "side": "CE"}, "NIFTY", on)
    assert inst.block({"bars1": bar("11:00")}, {"name": "NOISE_BREAKOUT", "side": "PE"}, "NIFTY", on) is None  # no trend data: no veto


def test_v3_ib_gate_pe_extra_and_inside_bar_policy():
    from app.modules.opportunities.service import institutional_filters as inst

    on = inst.enabled("IB_GATE,PE_EXTRA")
    bar = lambda hhmm, c=100.0: [{"t": f"2026-11-12T{hhmm}:00+05:30", "c": c}]  # noqa: E731
    lv = {"ibHigh": 101.0, "ibLow": 99.0, "pdc": 98.0, "gapPct": 0.1, "dayLow": 97.0, "dayHigh": 101.0}
    ce = {"name": "NOISE_BREAKOUT", "side": "CE"}
    # after 11:15: must be beyond the initial balance
    assert "inside the 09:15-11:15" in inst.block({"levels": lv, "bars1": bar("12:00", 100.0)}, ce, "NIFTY", on)
    assert inst.block({"levels": lv, "bars1": bar("12:00", 101.5)}, ce, "NIFTY", on) is None
    # before 11:15: only an unfilled open drive
    assert "open-drive" in inst.block({"levels": lv, "bars1": bar("10:30", 101.5)}, ce, "NIFTY", on)
    drive = {**lv, "gapPct": 0.6, "dayLow": 98.5}
    assert inst.block({"levels": drive, "bars1": bar("10:30", 101.5)}, ce, "NIFTY", on) is None
    # last entry 14:45 NSE / 14:30 BSE
    assert "no new entries" in inst.block({"levels": lv, "bars1": bar("14:40", 101.5)}, ce, "SENSEX", on)
    assert inst.block({"levels": lv, "bars1": bar("14:40", 101.5)}, ce, "NIFTY", on) is None
    # PE_EXTRA: short momentum needs trend efficiency or VIX up
    pe = {"name": "NOISE_BREAKOUT", "side": "PE"}
    base = {"levels": lv, "bars1": bar("12:00", 98.5)}
    assert "PE_EXTRA" in inst.block({**base, "er10": 0.1, "vix": {"changePct": -1.0}}, pe, "NIFTY", on)
    assert inst.block({**base, "er10": 0.3}, pe, "NIFTY", on) is None
    assert inst.block({**base, "er10": 0.1, "vix": {"changePct": 2.0}}, pe, "NIFTY", on) is None
    # INSIDE_BAR trades as a momentum entry, behind the same gates
    assert su.SETUP_POLICY["INSIDE_BAR"] == "CORE" and "INSIDE_BAR" in inst.MOMENTUM_SETUPS
    assert inst.block({"levels": lv, "bars1": bar("12:00", 100.0)}, {"name": "INSIDE_BAR", "side": "CE"}, "NIFTY", on)


def test_fii_open_drive_signal_window_and_exit():
    from app.core.config.settings import settings
    from app.modules.opportunities.service import fii_open
    from app.modules.trades.service.trade_service import _trade_close_at

    old = settings.FII_OPEN_CODES
    settings.FII_OPEN_CODES = "NIFTY"
    try:
        at = lambda h, m: datetime(2026, 11, 13, h, m, tzinfo=IST)  # noqa: E731
        s = fii_open.signal("NIFTY", 25000.0, at(9, 22), change=(5000.0, "2026-11-12"))
        assert s and s["side"] == "CE" and s["fixedStop"] and abs(s["stop"] - 24900.0) < 0.01 and s["target"] > 25000
        assert su.SETUP_POLICY[s["name"]] == "CORE"
        assert fii_open.signal("NIFTY", 25000.0, at(9, 22), change=(-10.0, "x")) is None  # FII net down: no trade
        assert fii_open.signal("NIFTY", 25000.0, at(9, 40), change=(5000.0, "x")) is None  # after the window
        assert fii_open.signal("SENSEX", 80000.0, at(9, 22), change=(5000.0, "x")) is None  # not configured
        settings.FII_OPEN_CODES = ""
        assert fii_open.signal("NIFTY", 25000.0, at(9, 22), change=(5000.0, "x")) is None  # switched off
    finally:
        settings.FII_OPEN_CODES = old
    close = datetime(2026, 11, 13, 15, 30, tzinfo=IST)
    now = datetime(2026, 11, 13, 9, 30, tzinfo=IST)
    assert _trade_close_at("FII_OPEN_DRIVE", close, now) == datetime(2026, 11, 13, 10, 30, tzinfo=IST)
    assert _trade_close_at("NOISE_BREAKOUT", close, now) == close
