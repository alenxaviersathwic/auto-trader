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
    assert ce and ce[0]["setup"] == "ORB" and ce[0]["costPct"] > 0
    assert all(x["setup"] is None for x in menu if x["side"] == "PE")


def test_costs_and_net_edge():
    c = round_trip_cost_pct(100, 65, "NSE", 6)
    assert 0.6 < c < 1.5
    assert expected_edge_pct(55, 6, 3, c) < expected_edge_pct(55, 6, 3, 0)


def test_session_blocks_and_mcx_dst_close():
    assert session_info("09:15", "15:40", datetime(2026, 11, 2, 9, 20, tzinfo=IST))["blocked"]
    assert session_info("09:15", "15:40", datetime(2026, 11, 2, 15, 20, tzinfo=IST))["blocked"]
    assert session_info("09:15", "15:40", datetime(2026, 11, 2, 10, 0, tzinfo=IST))["blocked"] is None
    gold = get_config("GOLD")
    assert gold.close_today(datetime(2026, 7, 1, 12, tzinfo=IST)) == "23:55"
    assert gold.close_today(datetime(2026, 12, 1, 12, tzinfo=IST)) == "23:30"


def test_resample_marks_open_bucket():
    bars = five(555, 1, 2) + [bar(560, 2, 3, 1, 2)]
    r = resample(bars, 5, "09:15", now_min=561)
    assert r[0]["done"] and not r[1]["done"]


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
