"""Human-style temporary view: 'bearish, likely 24,500; below it 24,450; wrong above X' (18 Nov 2026)."""
from app.modules.opportunity_finder.service import momentum_now, temp_view


def _bars(closes, wick=6.0):
    out, prev = [], closes[0]
    for c in closes:
        out.append({"o": prev, "h": max(prev, c) + wick, "l": min(prev, c) - wick, "c": c})
        prev = c
    return out


def _nifty_slide():
    # 24,700 -> ~24,540 over the last hour: a clean afternoon slide
    return _bars([24700 - i * 5 for i in range(33)])


def _analysis(bars, **kw):
    a = {"bars5": bars, "atr5": 22.0, "spot": bars[-1]["c"], "levels": {}, "oi": {},
         "vwap": {"value": bars[-1]["c"] + 40, "above": False, "distPct": -0.15}}
    a.update(kw)
    return a


def test_round_step_follows_atr():
    assert temp_view.round_step(22) == 50
    assert temp_view.round_step(80) == 100


def test_bearish_view_targets_round_then_next_round():
    a = _analysis(_nifty_slide())
    now = momentum_now.read(a)
    assert now["bias"] == "BEARISH"
    v = temp_view.build(a, now)
    assert v["bias"] == "BEARISH"
    t1, t2 = v["steps"]
    assert t1["level"] == 24500 and t1["if"] is None
    assert t2["level"] == 24450 and "below 24,500" in t2["if"]
    assert v["invalidation"]["level"] > a["spot"]
    assert "24,500" in v["text"] and "24,450" in v["text"]


def test_strong_level_labels_merge_with_round():
    a = _analysis(_nifty_slide(), levels={"s1": 24503.0}, oi={"support": 24450.0})
    v = temp_view.build(a, momentum_now.read(a))
    t1, t2 = v["steps"]
    assert t1["level"] == 24503.0 and "S1" in t1["label"] and "round" in t1["label"]
    assert t2["level"] == 24450.0 and t2["label"].startswith("PE OI wall")


def test_bullish_view_mirrors():
    bars = _bars([24400 + i * 5 for i in range(33)])
    a = _analysis(bars, vwap={"value": bars[-1]["c"] - 40, "above": True, "distPct": 0.15})
    v = temp_view.build(a, momentum_now.read(a))
    assert v["bias"] == "BULLISH"
    t1, t2 = v["steps"]
    assert a["spot"] < t1["level"] < t2["level"]
    assert v["invalidation"]["level"] < a["spot"]


def test_mixed_view_gives_range_and_both_breaks():
    bars = _bars([24600 + (8 if i % 2 else -8) for i in range(33)])
    a = _analysis(bars, vwap=None)
    now = {"bias": "MIXED", "score": 0, "minutes": 60}
    v = temp_view.build(a, now)
    assert v["range"]["support"]["level"] < a["spot"] < v["range"]["resistance"]["level"]
    assert v["steps"][0]["level"] < v["range"]["support"]["level"]
    assert v["steps"][1]["level"] > v["range"]["resistance"]["level"]
    assert v["invalidation"] is None


def test_no_now_read_gives_no_view():
    assert temp_view.build(_analysis(_nifty_slide()), None) is None
