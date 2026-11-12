"""Opportunity finding: instrument catalogue, MCX chain synthesis, analysis, coded setups, menu, costs."""

import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.modules.opportunities.provider.instrument_catalog import parse_rows
from app.modules.opportunities.provider.underlying_config import get_config
from app.modules.opportunities.provider.upstox_market_data import UpstoxMarketData
from app.modules.opportunities.provider.instrument_catalog import OptionContract
from app.modules.opportunities.service import setups as setup_detector
from app.modules.opportunities.service.costs import round_trip_cost_pct
from app.modules.opportunities.service.market_analysis import analyze, resample, session_info
from app.modules.opportunities.service.menu_builder import build_menu, expected_edge_pct

IST = ZoneInfo("Asia/Kolkata")
DAY = "2026-11-02"


def ms(d: str) -> int:
    return int(datetime.fromisoformat(d + "T15:30:00+05:30").timestamp() * 1000)


def bar(minute: int, o, h, l, c, v=1000, oi=100000):
    hh, mm = divmod(minute, 60)
    return {"t": f"{DAY}T{hh:02d}:{mm:02d}:00+05:30", "o": o, "h": h, "l": l, "c": c, "v": v, "oi": oi}


def five(minute: int, o, c, hi_pad=2, lo_pad=2, v=1000, oi=100000):
    """Five 1-minute bars that form one 5-minute bar o->c."""
    out, step = [], (c - o) / 5
    for i in range(5):
        a, b = o + step * i, o + step * (i + 1)
        out.append(bar(minute + i, a, max(a, b) + hi_pad / 5, min(a, b) - lo_pad / 5, b, v / 5, oi))
    return out


def daily(n=21, h=24200, l=23900, c=24050):
    rows = []
    for i in range(n):
        w = 300 + (i % 7) * 40  # varied widths so CPR rank is meaningful
        rows.append({"t": f"2026-10-{i + 1:02d}T00:00:00+05:30", "o": c, "h": c + w / 2, "l": c - w / 2, "c": c, "v": 0, "oi": 0})
    rows.append({"t": "2026-11-01T00:00:00+05:30", "o": c, "h": h, "l": l, "c": c, "v": 0, "oi": 0})
    return rows


def leg(key, ltp, delta, oi=50000, vol=2000, spread=0.5):
    return {"key": key, "ltp": ltp, "oi": oi, "volume": vol, "bid": ltp - spread / 2, "ask": ltp + spread / 2, "delta": delta, "iv": 14}


def chain(spot, step=50, expiry="2026-11-10"):
    rows = []
    for k in range(-5, 6):
        s = round(spot / step) * step + k * step
        dist = s - spot
        rows.append({"strike": s,
                     "CE": leg(f"CE{s}", max(5.0, 120 - dist * 0.55), max(0.05, min(0.95, 0.5 - dist / 400))),
                     "PE": leg(f"PE{s}", max(5.0, 120 + dist * 0.55), -max(0.05, min(0.95, 0.5 + dist / 400)))})
    return {"expiry": expiry, "spot": spot, "pcr": 1.0, "resistance": None, "support": None, "atmStraddle": 240.0, "strikes": rows}


# ───────────────────────── catalogue ─────────────────────────
def test_catalog_parses_mcx_lots_and_index_futures():
    mcx = [
        {"segment": "MCX_FO", "instrument_type": "CE", "underlying_symbol": "GOLD", "instrument_key": "MCX_FO|1",
         "underlying_key": "MCX_FO|900", "strike_price": 130000, "expiry": ms("2026-11-25"), "lot_size": 1, "qty_multiplier": 100},
        {"segment": "MCX_FO", "instrument_type": "FUT", "underlying_symbol": "GOLD", "instrument_key": "MCX_FO|900",
         "expiry": ms("2026-12-04"), "lot_size": 1, "qty_multiplier": 100},
        {"segment": "NSE_EQ", "instrument_type": "EQ", "underlying_symbol": "X", "instrument_key": "NSE_EQ|1"},
    ]
    opts, futs = parse_rows(mcx, "MCX")
    assert opts["GOLD"][0].lotUnits == 100 and opts["GOLD"][0].underlyingKey == "MCX_FO|900"
    assert opts["GOLD"][0].expiry == "2026-11-25" and futs["GOLD"][0].key == "MCX_FO|900"
    nse = [{"segment": "NSE_FO", "instrument_type": "FUT", "underlying_symbol": "NIFTY", "instrument_key": f"NSE_FO|{i}",
            "expiry": ms(d), "lot_size": 65} for i, d in enumerate(["2026-11-24", "2026-12-29"])]
    _, f = parse_rows(nse, "NSE")
    assert [x.expiry for x in f["NIFTY"]] == ["2026-11-24", "2026-12-29"]


# ───────────────────────── MCX chain synthesis ─────────────────────────
def test_mcx_chain_built_from_quotes_and_greeks():
    contracts = [OptionContract(f"MCX_FO|{s}{side}", "MCX_FO|900", side, float(s), "2026-11-17", 1250, "")
                 for s in (270, 275, 280, 285, 290) for side in ("CE", "PE")]

    def handler(req: httpx.Request) -> httpx.Response:
        keys = req.url.params["instrument_key"].split(",")
        if req.url.path.endswith("/option-greek"):
            data = {k: {"instrument_token": k, "delta": 0.5 if k.endswith("CE") else -0.5, "iv": 40} for k in keys}
        else:
            data = {}
            for k in keys:
                if k == "MCX_FO|900":
                    data["MCX_FO:NG"] = {"instrument_token": k, "last_price": 281.0}
                else:
                    data[k] = {"instrument_token": k, "last_price": 6.0, "oi": 900, "volume": 300,
                               "depth": {"buy": [{"price": 5.95, "quantity": 5}], "sell": [{"price": 6.05, "quantity": 4}]}}
        return httpx.Response(200, json={"status": "success", "data": data})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await UpstoxMarketData()._mcx_chain(c, "2026-11-17", contracts)

    ch = asyncio.run(run())
    assert ch["spot"] == 281.0 and len(ch["strikes"]) == 5
    s280 = next(s for s in ch["strikes"] if s["strike"] == 280)
    assert s280["CE"]["bid"] == 5.95 and s280["CE"]["ask"] == 6.05 and s280["CE"]["oi"] == 900
    assert s280["CE"]["delta"] == 0.5 and ch["atmStraddle"] == 12.0


# ───────────────────────── setups ─────────────────────────
def _orb_market():
    bars = five(555, 24000, 24030, 12, 8) + five(560, 24030, 24010, 8, 12) + five(565, 24010, 24035)  # OR 9:15-9:30
    bars += five(570, 24035, 24025) + five(575, 24025, 24032)
    bars += five(580, 24032, 24070, v=6000)  # 9:40 bar breaks the OR high with volume
    fut = [{**b, "c": b["c"] + 20, "o": b["o"] + 20, "h": b["h"] + 20, "l": b["l"] + 20} for b in bars]
    return {"spot": 24070, "spotBars1m": bars, "futBars1m": fut, "daily": daily(h=24250), "vix": {"value": 13, "changePct": 1},
            "chains": [chain(24070)], "lotUnits": 65}


def test_orb_fires_with_target_at_next_level():
    cfg = get_config("NIFTY")
    m = _orb_market()
    a = analyze(cfg, m, now=datetime(2026, 11, 2, 9, 45, 5, tzinfo=IST))
    assert a["levels"]["orHigh"] > 24030 and a["volume"]["spike"]
    found = setup_detector.detect(a, cfg)
    orb = next(s for s in found if s["name"] == "ORB")
    assert orb["side"] == "CE" and orb["target"] > orb["entry"] > orb["stop"] and orb["rr"] >= 1.3


def test_momentum_flag_like_screenshot():
    cfg = get_config("NIFTY")
    bars = five(555, 22400, 22405) + five(560, 22405, 22402) + five(565, 22402, 22408)
    bars += five(570, 22408, 22470, v=5000) + five(575, 22470, 22525, v=5000)  # impulse ~ +117
    bars += five(580, 22525, 22510) + five(585, 22510, 22518) + five(590, 22518, 22512)  # tight pause in the top half
    bars += five(595, 22512, 22540, v=4000)  # break of the pause high
    m = {"spot": 22540, "spotBars1m": bars, "futBars1m": bars, "daily": daily(h=22660, l=22300, c=22400),
         "vix": None, "chains": [chain(22540)], "lotUnits": 65}
    a = analyze(cfg, m, now=datetime(2026, 11, 2, 10, 0, 5, tzinfo=IST))
    flag = next(s for s in setup_detector.detect(a, cfg) if s["name"] == "MOMENTUM_FLAG")
    assert flag["side"] == "CE" and flag["stop"] < 22510 and flag["target"] >= 22600


def test_menu_uses_setup_levels_and_costs():
    cfg = get_config("NIFTY")
    m = _orb_market()
    a = analyze(cfg, m, now=datetime(2026, 11, 2, 9, 45, 5, tzinfo=IST))
    found = setup_detector.detect(a, cfg)
    menu = build_menu(cfg, m, "BULLISH", 5.0, setups=found)
    ce = [x for x in menu if x["side"] == "CE"]
    assert ce and ce[0]["setup"] == "ORB" and ce[0]["costPct"] > 0 and ce[0]["exitMode"] == "PCT"
    assert all(x["setup"] is None for x in menu if x["side"] == "PE")


def test_costs_and_net_edge():
    c = round_trip_cost_pct(100, 65, "NSE", 6)
    assert 0.6 < c < 1.5
    assert expected_edge_pct(55, 6, 3, c) < expected_edge_pct(55, 6, 3, 0)


def test_session_blocks_and_mcx_dst_close():
    assert session_info("09:15", "15:40", datetime(2026, 11, 2, 9, 18, tzinfo=IST))["blocked"]  # first 5 minutes
    assert session_info("09:15", "15:40", datetime(2026, 11, 2, 9, 21, tzinfo=IST))["blocked"] is None
    assert session_info("09:15", "15:40", datetime(2026, 11, 2, 12, 30, tzinfo=IST))["blocked"]  # 12:00-13:00 chop
    assert session_info("09:15", "15:40", datetime(2026, 11, 2, 13, 1, tzinfo=IST))["blocked"] is None
    assert session_info("09:15", "15:40", datetime(2026, 11, 2, 15, 20, tzinfo=IST))["blocked"] is None  # 20 min left
    assert session_info("09:15", "15:40", datetime(2026, 11, 2, 15, 21, tzinfo=IST))["blocked"]
    assert session_info("09:15", "15:40", datetime(2026, 11, 2, 10, 0, tzinfo=IST))["blocked"] is None
    gold = get_config("GOLD")
    assert gold.close_today(datetime(2026, 7, 1, 12, tzinfo=IST)) == "23:55"
    assert gold.close_today(datetime(2026, 12, 1, 12, tzinfo=IST)) == "23:30"


def test_resample_marks_open_bucket():
    bars = five(555, 1, 2) + [bar(560, 2, 3, 1, 2)]
    r = resample(bars, 5, "09:15", now_min=561)
    assert r[0]["done"] and not r[1]["done"]


def _rising_1m(n=8, start=100.0, step=0.5):
    """n green 1-minute bars stepping up (higher lows, closes above a rising EMA9)."""
    return [bar(595 + i, start + step * i, start + step * i + 0.6, start + step * i - 0.1, start + step * (i + 1))
            for i in range(n)]


def _a(**kw):
    base = {"trend15": "UP", "atr5": 10.0, "bars1": _rising_1m()}
    base.update(kw)
    return base


def test_timeframes_must_agree():
    ce = {"name": "NOISE_BREAKOUT", "side": "CE", "strength": 3, "entry": 103.0, "stop": 95.0, "target": 120.0}
    pe = {"name": "NOISE_BREAKOUT", "side": "PE", "strength": 3, "entry": 103.0, "stop": 110.0, "target": 90.0}
    ok, rej = setup_detector.confirm_timeframes(_a(), [ce, pe])
    assert [s["side"] for s in ok] == ["CE"] and "15-min trend" in rej[0]["reason"]
    assert ok[0]["timeframes"]["1m"] == "confirmed" and ok[0]["trigger1m"] > ok[0]["entry1m"]
    # one red 1-minute bar above the 1-min EMA9 with no fresh low no longer vetoes a CE (it flickered every 20 s)
    red = _rising_1m()[:-1] + [bar(603, 104.5, 104.6, 103.6, 103.8)]
    ok, rej = setup_detector.confirm_timeframes(_a(bars1=red), [ce])
    assert ok
    ok, rej = setup_detector.confirm_timeframes(_a(bars1=[]), [ce])
    assert not ok and "completed 1-min bars" in rej[0]["reason"]


def test_one_minute_chart_always_checked():
    ce = {"name": "NOISE_BREAKOUT", "side": "CE", "strength": 3, "entry": 103.0, "stop": 95.0, "target": 120.0}
    # below the 1-min EMA9: a long run of falling bars, then one small green bar
    falling = [bar(590 + i, 110 - i, 110.2 - i, 108.9 - i, 109 - i) for i in range(10)]
    falling.append(bar(600, 100.0, 100.4, 99.8, 100.3))
    ok, rej = setup_detector.confirm_timeframes(_a(bars1=falling), [ce])
    assert not ok and "EMA9" in rej[0]["reason"]
    # setup stop touched on the 1-min chart
    ok, rej = setup_detector.confirm_timeframes(_a(), [{**ce, "stop": 102.0}])
    assert not ok and "touched the setup stop" in rej[0]["reason"]
    # chasing: 1-min close far past the setup entry (> 0.5 x ATR5 = 5 pts)
    ok, rej = setup_detector.confirm_timeframes(_a(), [{**ce, "entry": 96.0, "stop": 90.0}])
    assert not ok and "chasing" in rej[0]["reason"]
    # target already reached on the 1-min chart
    ok, rej = setup_detector.confirm_timeframes(_a(), [{**ce, "target": 103.5}])
    assert not ok and "target" in rej[0]["reason"]


def _bars5(specs, start=555):
    """specs: list of (o, h, l, c) -> completed 5-minute bars as the setups see them."""
    return [{"t": "", "o": o, "h": h, "l": l, "c": c, "v": 1000, "oi": 0, "start": start + 5 * i, "done": True}
            for i, (o, h, l, c) in enumerate(specs)]


def _setup_input(bars, **extra):
    a = {"bars5": bars, "atr5": 10.0, "regime": "MIXED", "trend15": "UP", "levels": {}, "keyLevels": [],
         "session": {"minutesSinceOpen": 40}}
    a.update(extra)
    return a


def test_inside_bar_breakout():
    cfg = get_config("NIFTY")
    bars = _bars5([(100, 101, 99, 100)] * 4 + [(100, 120, 98, 118), (110, 115, 105, 112), (112, 128, 111, 126)])
    names = {(s["name"], s["side"]) for s in setup_detector.detect(_setup_input(bars), cfg)}
    assert ("INSIDE_BAR", "CE") in names


def test_range_breakout():
    cfg = get_config("NIFTY")
    box = [(100, 104, 98, 101), (101, 105, 99, 102)] * 4
    bars = _bars5(box + [(102, 122, 101, 121)])
    names = {(s["name"], s["side"]) for s in setup_detector.detect(_setup_input(bars), cfg)}
    assert ("RANGE_BREAKOUT", "CE") in names


def test_gap_go_and_short_covering_and_pcr():
    cfg = get_config("NIFTY")
    bars = _bars5([(100, 102, 99, 101)] * 4 + [(101, 105, 100, 104), (104, 109, 103, 108)])
    lv = {"gapPct": 0.6, "pdc": 96.0, "dayOpen": 99.0, "dayLow": 98.5, "dayHigh": 109}
    vw = {"value": 107.8, "futLast": 108.0, "above": True, "distPct": 0.2}
    vw_series = [100.0] * len(bars)
    found = setup_detector.detect(_setup_input(bars, levels=lv, vwap=vw, vwapSeries5=vw_series, futBars5=bars), cfg)
    assert any(s["name"] == "GAP_GO" and s["side"] == "CE" for s in found)

    vol = {"spike": True, "ratio5m": 2.0, "dry": False, "lastBarUp": True}
    bu = {"state": "SHORT_COVERING", "priceChgPct": 0.4, "oiChgPct": -0.6}
    found = setup_detector.detect(_setup_input(bars, volume=vol, buildup=bu), cfg)
    assert any(s["name"] == "SHORT_COVERING_SPIKE" and s["side"] == "CE" for s in found)

    # PCR_SHIFT demoted 10 Nov 2026 (weak/no predictive power on NSE intraday returns -- Jena, Tiwari & Mitra
    # 2019): an OI shift must never fire a setup on its own any more, only nudge confidence via
    # menu_builder.pcr_adjustment() on whatever other setup already fired.
    shift = {"pcrChg": 0.12, "peOiChgPct": 3.0, "ceOiChgPct": 0.5, "pcr": 1.1}
    found = setup_detector.detect(_setup_input(bars, oiShift=shift), cfg)
    assert not any(s["name"] == "PCR_SHIFT" for s in found)


def test_ema_cross_retest_and_supertrend():
    cfg = get_config("NIFTY")
    down = [(130 - i, 131 - i, 129 - i, 129.5 - i) for i in range(12)]  # downtrend
    up = [(118 + 3 * i, 120 + 3 * i, 117 + 3 * i, 119.5 + 3 * i) for i in range(8)]  # sharp reversal up
    bars = _bars5(down + up)
    pull = (bars[-1]["c"], bars[-1]["c"] + 1, bars[-1]["c"] - 9, bars[-1]["c"] - 6)
    resume = (pull[3], pull[3] + 14, pull[3] - 1, pull[3] + 12)
    bars = _bars5(down + up + [pull, resume])
    from app.modules.opportunities.service.market_analysis import ema, supertrend
    closes = [b["c"] for b in bars]
    a = _setup_input(bars, emaSeries5={"e9": ema(closes, 9)[-14:], "e21": ema(closes, 21)[-14:]},
                     supertrend5=supertrend(bars))
    assert a["supertrend5"] is not None and a["supertrend5"]["dir"] == "UP"
    found = setup_detector.detect(a, cfg)
    assert {s["name"] for s in found} & {"EMA_CROSS_RETEST", "SUPERTREND_RETEST", "SUPERTREND_FLIP"}


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("PASS", name)
            except Exception as e:
                fails += 1
                import traceback
                print("FAIL", name, type(e).__name__, e)
                traceback.print_exc(limit=2)
    raise SystemExit(fails)


def test_flat_15m_trend_vetoes_trend_setups_only(monkeypatch):
    # family mechanics (still in the code for research replays): policy opened up for this test only
    monkeypatch.setattr(setup_detector, "policy_block", lambda a, s: None)
    ce = {"name": "ORB", "side": "CE", "strength": 3, "entry": 103.0, "stop": 95.0, "target": 120.0}
    rng = {**ce, "name": "PDH_PDL_RETEST"}
    rev = {**ce, "name": "FAILED_BREAK_RECLAIM"}
    ok, rej = setup_detector.confirm_timeframes(_a(trend15="FLAT"), [ce, rng, rev])
    assert [s["name"] for s in ok] == ["PDH_PDL_RETEST", "FAILED_BREAK_RECLAIM"]
    assert rej[0]["name"] == "ORB" and "FLAT" in rej[0]["reason"]
    # against the 15-minute trend: only the reversal family may trade
    ok, rej = setup_detector.confirm_timeframes(_a(trend15="DOWN"), [ce, rng, rev])
    assert [s["name"] for s in ok] == ["FAILED_BREAK_RECLAIM"] and ok[0]["family"] == "REVERSAL"


def _v_day_market():
    """NIFTY 9 Nov 2026 shape: holds above the S1-ish level, breaks it, then closes back above (failed breakdown)."""
    bars = []
    px = 25070.0
    t = 555
    for _ in range(6):  # drifting lower but above 25000
        bars += five(t, px, px - 8, v=1000)
        px -= 8
        t += 5
    bars += five(t, px, 24985, v=1500)  # breaks 25000 (the put-OI strike)
    t += 5
    bars += five(t, 24985, 24978, v=1500)
    t += 5
    bars += five(t, 24978, 25012, v=3000)  # closes back above 25000 -> reclaim
    ch = chain(25010)
    ch["support"] = 25000.0
    ch["resistance"] = 25100.0
    return {"spot": 25012, "spotBars1m": bars, "futBars1m": bars, "daily": daily(h=25200, l=24700, c=25076),
            "vix": None, "chains": [ch], "lotUnits": 65}


def test_failed_breakdown_reclaim_fires():
    cfg = get_config("NIFTY")
    a = analyze(cfg, _v_day_market(), now=datetime(2026, 11, 9, 10, 2, 5, tzinfo=IST))
    rec = [s for s in setup_detector.detect(a, cfg) if s["name"] == "FAILED_BREAK_RECLAIM"]
    assert rec and rec[0]["side"] == "CE" and "failed breakdown" in rec[0]["reason"]
    assert rec[0]["stop"] < 24978 and rec[0]["target"] > rec[0]["entry"]


def test_no_reclaim_when_the_level_never_held():
    """A rally from below a level is not a failed breakdown of it (the ORB market opens under BC)."""
    cfg = get_config("NIFTY")
    a = analyze(cfg, _orb_market(), now=datetime(2026, 11, 2, 9, 45, 5, tzinfo=IST))
    assert not [s for s in setup_detector.detect(a, cfg) if s["name"] == "FAILED_BREAK_RECLAIM"]


def test_point_based_exits_follow_the_chart_not_a_fixed_percent():
    cfg = get_config("NIFTY")
    m = _orb_market()
    a = analyze(cfg, m, now=datetime(2026, 11, 2, 9, 45, 5, tzinfo=IST))
    found = setup_detector.detect(a, cfg)
    menu = build_menu(cfg, m, "BULLISH", 1.0, max_stop=3.0, max_margin=6.0, setups=found, atr5=a["atr5"])
    ce = [x for x in menu if x["side"] == "CE" and x["setup"]]
    assert ce and all(x["exitMode"] == "POINTS" for x in ce)
    x = ce[0]
    stop_pts = x["entry"] * x["stopPct"] / 100 / x["delta"]
    assert 0.5 * a["atr5"] - 0.5 <= stop_pts <= 1.25 * a["atr5"] + 0.5
    assert x["rewardRisk"] >= 1.2


def test_expiry_day_after_1330_is_itm_only(monkeypatch):
    from app.modules.opportunities.service import menu_builder as mb

    cfg = get_config("NIFTY")
    m = _orb_market()
    a = analyze(cfg, m, now=datetime(2026, 11, 2, 9, 45, 5, tzinfo=IST))
    found = setup_detector.detect(a, cfg)
    monkeypatch.setattr(mb, "_is_0dte_blocked", lambda expiry, now=None: True)
    reasons: dict = {}
    menu = mb.build_menu(cfg, m, "BULLISH", 1.0, setups=found, reasons=reasons, atr5=a["atr5"])
    assert all(x["delta"] >= mb.EXPIRY_ITM_DELTA for x in menu)
    assert reasons.get("expiry-day after 13:30 needs ITM", 0) >= 1


def test_vwap_band_fade_on_a_flat_vwap_day():
    b = lambda o, h, l, c: {"t": "2026-11-09T11:00:00+05:30", "o": o, "h": h, "l": l, "c": c, "v": 1000, "oi": 0}
    bars = [b(25000, 25010, 24995, 25005), b(25005, 25062, 25004, 25058), b(25058, 25060, 25035, 25038)]
    a = {"bars5": bars, "futBars5": bars, "atr5": 20.0, "regime": "RANGE", "trend15": "FLAT", "levels": {},
         "keyLevels": [], "vwap": {"value": 25000.0, "sd": 25.0, "slopePct": 0.01, "above": True}}
    fade = [s for s in setup_detector.detect(a, get_config("NIFTY")) if s["name"] == "VWAP_BAND_REVERT"]
    assert fade and fade[0]["side"] == "PE" and fade[0]["targetLevel"] == "VWAP"
    assert fade[0]["target"] == 25000.0 and fade[0]["stop"] > 25062
    a["vwap"]["slopePct"] = 0.2  # trending VWAP: no fade
    assert not [s for s in setup_detector.detect(a, get_config("NIFTY")) if s["name"] == "VWAP_BAND_REVERT"]


def test_setup_policy_keeps_only_institutional_momentum_as_option_buys():
    base = {"side": "CE", "strength": 3, "entry": 103.0, "stop": 95.0, "target": 120.0}
    names = ["NOISE_BREAKOUT", "ORB", "PDH_PDL_RETEST", "FAILED_BREAK_RECLAIM", "RANGE_BREAKOUT", "BRAND_NEW_SETUP"]
    ok, rej = setup_detector.confirm_timeframes(_a(), [{**base, "name": n} for n in names])
    assert [s["name"] for s in ok] == ["NOISE_BREAKOUT"]
    why = {r["name"]: r["reason"] for r in rej}
    assert "dropped" in why["ORB"] and "dropped" in why["PDH_PDL_RETEST"] and "dropped" in why["BRAND_NEW_SETUP"]
    assert "short-premium placement only" in why["FAILED_BREAK_RECLAIM"]
    assert "only inside an active CE noise breakout" in why["RANGE_BREAKOUT"]
    ok, _ = setup_detector.confirm_timeframes(_a(dayType={"type": "EXPANSION", "side": "CE"}),
                                              [{**base, "name": "RANGE_BREAKOUT"}])
    assert [s["name"] for s in ok] == ["RANGE_BREAKOUT"]
