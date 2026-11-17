"""The "now" read must see an afternoon sell-off that the whole-day read misses (SENSEX, 17 Nov 2026)."""
from app.modules.opportunity_finder.service import momentum_now


def _bars(closes, wick=15.0):
    out, prev = [], closes[0]
    for c in closes:
        out.append({"o": prev, "h": max(prev, c) + wick, "l": min(prev, c) - wick, "c": c})
        prev = c
    return out


def _sensex_afternoon():
    # morning trend up, a midday dip, a rally to ~82,800 by 14:30, then a slide to 82,578 by 15:07
    up = [82000 + i * 30 for i in range(20)]  # to ~82,570
    dip = [82570 - i * 20 for i in range(8)]  # to ~82,430
    rally = [82430 + i * 37 for i in range(11)]  # to ~82,800
    slide = [82800 - i * 32 for i in range(8)]  # to ~82,576
    return _bars(up + dip + rally + slide)


def test_afternoon_selloff_reads_bearish_now():
    a = {"bars5": _sensex_afternoon(), "atr5": 45.0,
         "vwap": {"value": 82650.0, "above": False, "distPct": -0.09}}
    r = momentum_now.read(a)
    assert r is not None
    assert r["bias"] == "BEARISH", r
    labels = {v["label"]: v["vote"] for v in r["votes"]}
    assert labels["5-min EMAs"] <= 0  # the 21 EMA lags a fresh turn; the other votes catch it
    assert labels["VWAP"] == -1
    assert labels["Off the high"] == -1


def test_steady_rally_reads_bullish_now():
    a = {"bars5": _bars([82000 + i * 25 for i in range(30)]), "atr5": 40.0,
         "vwap": {"value": 82200.0, "above": True, "distPct": 0.4}}
    r = momentum_now.read(a)
    assert r["bias"] == "BULLISH", r
    assert not any(v["label"].startswith("Off the") for v in r["votes"])


def test_too_few_bars_gives_no_read():
    assert momentum_now.read({"bars5": _bars([1, 2, 3]), "atr5": 1.0}) is None


def test_no_vwap_still_reads():
    r = momentum_now.read({"bars5": _sensex_afternoon(), "atr5": 45.0})
    assert r is not None and all(v["label"] != "VWAP" for v in r["votes"])


def test_index_institutional_filters_do_not_apply_to_mcx():
    """ENTRY_10_1430 is NSE-hours research: it must not block a crude entry at 16:20 (MCX trades to 23:30)."""
    from app.modules.opportunity_finder.service import institutional_filters as inst

    a = {"bars1": [{"t": "2026-11-17T16:20:00+05:30", "o": 1, "h": 1, "l": 1, "c": 1}], "levels": {}}
    s = {"name": "INSIDE_BAR", "side": "PE"}
    on = {"ENTRY_10_1430", "PE_EXTRA"}
    assert inst.block(a, s, "CRUDEOIL", on) is None
    assert inst.block(a, s, "NIFTY", on).startswith("ENTRY_10_1430")
