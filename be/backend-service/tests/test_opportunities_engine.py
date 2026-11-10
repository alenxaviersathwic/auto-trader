from datetime import datetime

import pytest

from app.modules.opportunities.graph import nodes
from app.modules.opportunities.graph.builder import underlying_graph
from app.modules.opportunities.provider.underlying_config import get_config
from app.modules.opportunities.schema.opportunity_schema import AiAnswer, AiPick
from app.modules.opportunities.service.menu_builder import build_menu, direction_bias


def _leg(key, ltp, delta):
    return {"key": key, "ltp": ltp, "oi": 50000, "volume": 900, "bid": ltp - 0.5, "ask": ltp + 0.5, "delta": delta}


def _market():
    strikes = [
        {"strike": s, "CE": _leg(f"CE{s}", 120 - (s - 24000) / 10, 0.5), "PE": _leg(f"PE{s}", 100 + (s - 24000) / 10, -0.5)}
        for s in (23900, 23950, 24000, 24050, 24100)
    ]
    chain = {"expiry": "2026-10-29", "spot": 24000.0, "pcr": 1.2, "resistance": 24200.0, "support": 23850.0,
             "strikes": strikes}
    return {"spot": 24000.0, "candles": {"trendPct": 0.4, "volumeRatio": 1.8, "lastCandleUp": True}, "chains": [chain],
            "fetchedAt": datetime.utcnow().isoformat()}


class _Ctx:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *a):
        return False


def test_direction_bias():
    assert direction_bias({"direction": "BULLISH"}, {"trend15": "UP"}) == "BULLISH"
    assert direction_bias({"direction": "BEARISH"}, {"trend15": "DOWN"}) == "BEARISH"
    assert direction_bias({}, {"trend15": "FLAT"}) == "NEUTRAL"
    assert direction_bias({}, {"trend15": "FLAT", "vwap": {"above": True}}) == "BULLISH"


def test_menu_keeps_call_and_put_whatever_the_trend():
    menu = build_menu(get_config("NIFTY"), _market(), "BULLISH", 10.0)
    assert {m["side"] for m in menu} == {"CE", "PE"}
    assert all(m["marginPct"] >= 10.0 and m["target"] > m["entry"] > m["stop"] for m in menu)
    assert all(m["withTrend"] == (m["side"] == "CE") for m in menu)


@pytest.fixture
def patched(monkeypatch):
    async def fake_fetch(cfg, s):
        return _market()

    async def fake_recall(*a, **k):
        return []

    async def no_strats(*a, **k):
        return [{"name": "Resistance Rejection", "bias": "BEARISH", "optionSide": "PE", "description": "x"}]

    fake_setups = [
        {"name": "ORB", "side": "CE", "strength": 3, "reason": "test", "entry": 24000.0, "stop": 23950.0,
         "target": 24100.0, "targetLevel": "pdh", "rr": 2.0, "withTrend": True, "conflict": None},
        {"name": "ORB", "side": "PE", "strength": 3, "reason": "test", "entry": 24000.0, "stop": 24050.0,
         "target": 23900.0, "targetLevel": "pdl", "rr": 2.0, "withTrend": False, "conflict": None},
    ]
    monkeypatch.setattr(nodes.setup_detector, "detect", lambda a, cfg: fake_setups)
    monkeypatch.setattr(nodes.setup_detector, "confirm_timeframes", lambda a, found: (found, []))
    monkeypatch.setattr(nodes, "async_session_factory", lambda: _Ctx())
    monkeypatch.setattr(nodes.market_data, "fetch", fake_fetch)

    async def fake_hit(*a, **k):
        return "no history yet"

    monkeypatch.setattr(nodes.memory_service, "recall", fake_recall)
    monkeypatch.setattr(nodes.memory_service, "hit_rate", fake_hit)
    monkeypatch.setattr(nodes._strategy_service, "list_suggestable_summaries", no_strats)

    async def no_time_machine(state):
        return None

    monkeypatch.setattr(nodes, "_time_machine_context", no_time_machine)
    nodes._last_answer.clear()


def _payload(conf=80):
    return {"masterId": 1, "code": "NIFTY", "research": {"direction": "BULLISH"},
            "params": {"confidenceWanted": conf, "minProfitMargin": 10.0, "ignoreMarketHours": True}}


@pytest.mark.asyncio
async def test_invalid_ai_id_retries_then_uses_baseline(patched, monkeypatch):
    async def healthy():
        return "http://x"

    async def fake_ai(msgs, schema, system_prompt=None, **k):
        return AiAnswer(picks=[AiPick(id="FAKE-1", confidence=99)])

    monkeypatch.setattr(nodes._llm, "_resolve_healthy_url", healthy)
    monkeypatch.setattr(nodes._llm, "generate_structured", fake_ai)
    out = await underlying_graph.ainvoke(_payload(conf=50))
    assert out["usedBaseline"] is True
    assert "FAKE-1" not in [c["id"] for c in out["candidates"]]


@pytest.mark.asyncio
async def test_valid_ai_pick_and_confidence_threshold(patched, monkeypatch):
    async def healthy():
        return "http://x"

    async def fake_ai(msgs, schema, system_prompt=None, **k):
        return AiAnswer(picks=[AiPick(id="NIFTY-2026-10-29-24000-CE", confidence=85, strategy="trend"),
                               AiPick(id="NIFTY-2026-10-29-23950-CE", confidence=60)])

    monkeypatch.setattr(nodes._llm, "_resolve_healthy_url", healthy)
    monkeypatch.setattr(nodes._llm, "generate_structured", fake_ai)
    out = await underlying_graph.ainvoke(_payload(conf=70))
    assert [c["id"] for c in out["candidates"]] == ["NIFTY-2026-10-29-24000-CE"]
    assert out["candidates"][0]["source"] == "AI"


@pytest.mark.asyncio
async def test_ai_down_falls_back_to_baseline(patched, monkeypatch):
    async def unhealthy():
        return None

    monkeypatch.setattr(nodes._llm, "_resolve_healthy_url", unhealthy)
    # The AI is only a ranker: with it down, the code-only ranking of the validated menu still produces picks,
    # but cannot clear an unrealistically high confidence bar.
    out = await underlying_graph.ainvoke(_payload(conf=50))
    assert out["usedBaseline"] is True and out["candidates"]
    assert all(c["source"] == "BASELINE" for c in out["candidates"])
    out = await underlying_graph.ainvoke(_payload(conf=95))
    assert out["candidates"] == [] and out["diag"]["result"] == "DROPPED"


@pytest.mark.asyncio
async def test_unchanged_brief_reuses_last_answer(patched, monkeypatch):
    calls = {"n": 0}

    async def healthy():
        return "http://x"

    async def fake_ai(msgs, schema, system_prompt=None, **k):
        calls["n"] += 1
        return AiAnswer(picks=[AiPick(id="NIFTY-2026-10-29-24000-CE", confidence=90)])

    monkeypatch.setattr(nodes._llm, "_resolve_healthy_url", healthy)
    monkeypatch.setattr(nodes._llm, "generate_structured", fake_ai)
    await underlying_graph.ainvoke(_payload())
    out = await underlying_graph.ainvoke(_payload())
    assert calls["n"] == 1 and out["reused"] is True and out["candidates"]


def test_bearish_trend_tags_calls_as_against_trend():
    assert direction_bias({"direction": "BEARISH"}, {"trend15": "UP"}) == "BEARISH"
    menu = build_menu(get_config("NIFTY"), _market(), "BEARISH", 5.0)
    assert any(m["side"] == "CE" and not m["withTrend"] for m in menu)
    assert any(m["side"] == "PE" and m["withTrend"] for m in menu)


@pytest.mark.asyncio
async def test_against_trend_put_needs_a_listed_strategy(patched, monkeypatch):
    async def healthy():
        return "http://x"

    async def fake_ai(msgs, schema, system_prompt=None, **k):
        return AiAnswer(picks=[
            AiPick(id="NIFTY-2026-10-29-24000-PE", confidence=85, strategy="Resistance Rejection"),
            AiPick(id="NIFTY-2026-10-29-24050-PE", confidence=85, strategy="made up"),
        ])

    monkeypatch.setattr(nodes._llm, "_resolve_healthy_url", healthy)
    monkeypatch.setattr(nodes._llm, "generate_structured", fake_ai)
    out = await underlying_graph.ainvoke(_payload(conf=70))  # research BULLISH => PE is against the trend
    ids = [c["id"] for c in out["candidates"]]
    # a contract on a validated setup is a legitimate against-trend trade (the citation rule only guards setup-less picks)
    assert ids == ["NIFTY-2026-10-29-24000-PE", "NIFTY-2026-10-29-24050-PE"]
    assert out["candidates"][0]["risks"][0].startswith("Against the bullish trend")


def test_volume_confirmation_and_dry_market():
    from app.modules.opportunities.service.menu_builder import volume_adjustment, volume_confirms

    up_high = {"volume": {"ratio5m": 1.8, "spike": True, "dry": False, "lastBarUp": True}}
    assert volume_confirms(up_high, "CE") and not volume_confirms(up_high, "PE")
    assert volume_adjustment(up_high, "CE") > 0
    assert volume_adjustment({"volume": {"ratio5m": 0.3, "spike": False, "dry": True, "lastBarUp": True}}, "CE") < 0
    assert volume_adjustment({"volume": {"ratio5m": 1.0, "spike": False, "dry": False, "lastBarUp": True}}, "CE") == 0


def test_market_hours_gate():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.modules.opportunities.provider.underlying_config import is_market_open

    tz = ZoneInfo("Asia/Kolkata")
    crude, nifty = get_config("CRUDEOIL"), get_config("NIFTY")
    assert is_market_open(crude, datetime(2026, 10, 27, 20, 0, tzinfo=tz))  # Tue 8pm: MCX open
    assert not is_market_open(nifty, datetime(2026, 10, 27, 20, 0, tzinfo=tz))
    assert not is_market_open(crude, datetime(2026, 10, 31, 12, 0, tzinfo=tz))  # Saturday


@pytest.mark.asyncio
async def test_closed_market_gives_a_reason_not_silence(patched, monkeypatch):
    p = _payload()
    p["params"]["ignoreMarketHours"] = False
    monkeypatch.setattr(nodes, "is_market_open", lambda cfg: False)
    out = await underlying_graph.ainvoke(p)
    assert "market closed" in out["error"] and not out.get("candidates")


def test_small_profit_band_and_tight_stop():
    menu = build_menu(get_config("NIFTY"), _market(), "NEUTRAL", 5.0, max_margin=10.0, max_stop=5.0)
    assert menu
    for m in menu:
        assert 5.0 <= m["marginPct"] <= 10.0
        assert 2.5 <= m["stopPct"] <= 5.0
        assert m["spreadPct"] <= 1.5


def test_reversal_setups_get_a_tighter_atm_stop_than_other_families():
    """10 Nov 2026 fix: FAILED_BREAK_RECLAIM (family REVERSAL) trades ATM against the day's trend/bias, so a wrong
    reclaim should cost less than a trend-aligned or range setup's full 1.25x-ATR stop."""
    market, atr5 = _market(), 20.0
    base_setup = {"side": "CE", "name": "X", "strength": 3, "target": 24500.0, "stop": 23700.0}

    def stop_pct_for(family: str) -> float:
        menu = build_menu(get_config("NIFTY"), market, "NEUTRAL", 1.0, setups=[{**base_setup, "family": family}],
                           require_setup=True, atr5=atr5, max_stop=50.0, max_margin=50.0)
        ce = next(m for m in menu if m["side"] == "CE" and m["setup"] == "X")
        return ce["stopPct"]

    reversal_stop = stop_pct_for("REVERSAL")
    range_stop = stop_pct_for("RANGE")
    trend_stop = stop_pct_for("TREND")
    assert reversal_stop < range_stop == trend_stop
    assert reversal_stop == pytest.approx(range_stop * (0.8 / 1.25), rel=0.01)


def test_pcr_adjustment_is_confluence_only_and_small():
    from app.modules.opportunities.service.menu_builder import PCR_BONUS, pcr_adjustment

    bullish_shift = {"pcrChg": 0.12, "peOiChgPct": 3.0, "ceOiChgPct": 0.5, "pcr": 1.1}
    assert pcr_adjustment({"oiShift": bullish_shift}, "CE") == PCR_BONUS
    assert pcr_adjustment({"oiShift": bullish_shift}, "PE") == 0
    bearish_shift = {"pcrChg": -0.12, "peOiChgPct": 0.5, "ceOiChgPct": 3.0, "pcr": 0.8}
    assert pcr_adjustment({"oiShift": bearish_shift}, "PE") == PCR_BONUS
    assert pcr_adjustment({}, "CE") == 0
    # weaker evidence than a coded setup (SETUP_BONUS) or a volume spike (VOLUME_BONUS): never the deciding factor
    from app.modules.opportunities.service.menu_builder import SETUP_BONUS, VOLUME_BONUS
    assert PCR_BONUS < SETUP_BONUS and PCR_BONUS < VOLUME_BONUS


def test_expected_edge_needs_real_probability():
    from app.modules.opportunities.service.menu_builder import expected_edge_pct

    assert expected_edge_pct(70, 7.5, 3.75) > 3
    assert expected_edge_pct(30, 7.5, 3.75) < 0



@pytest.mark.asyncio
async def test_no_setup_means_no_menu_and_a_diagnosis(patched, monkeypatch):
    monkeypatch.setattr(nodes.setup_detector, "detect", lambda a, cfg: [])
    out = await underlying_graph.ainvoke(_payload())
    assert not out.get("candidates") and out["diag"]["result"] == "NO_SETUP"


@pytest.mark.asyncio
async def test_setup_failing_timeframes_is_reported(patched, monkeypatch):
    rejected = [{"name": "ORB", "side": "CE", "reason": "15-min trend is FLAT, needs UP"}]
    monkeypatch.setattr(nodes.setup_detector, "confirm_timeframes", lambda a, found: ([], rejected))
    out = await underlying_graph.ainvoke(_payload())
    assert out["diag"]["result"] == "SETUP_REJECTED" and out["diag"]["setupsRejected"] == rejected


@pytest.mark.asyncio
async def test_menu_is_atm_or_one_itm_with_delta_floor(patched, monkeypatch):
    async def unhealthy():
        return None

    monkeypatch.setattr(nodes._llm, "_resolve_healthy_url", unhealthy)
    out = await underlying_graph.ainvoke(_payload(conf=40))
    for m in out["menu"]:
        assert m["delta"] >= 0.5
        assert m["strike"] in ((24000, 23950) if m["side"] == "CE" else (24000, 24050))
        assert m["setup"] == "ORB"


@pytest.mark.asyncio
async def test_time_machine_drops_the_side_history_runs_against(patched, monkeypatch):
    """A falling history: the PE plan leans to its target and is kept with the odds; the CE plan is dropped."""
    import random

    from app.modules.opportunities.service import timemachine as tm

    rnd = random.Random(5)
    bars = []
    for d in range(30):
        p = 24000.0
        for i in range(75):
            mins = 9 * 60 + 15 + 5 * i
            o, c = p, p * (1 - 0.0008 + rnd.gauss(0, 0.0005))
            bars.append({"t": f"2026-09-{d + 1:02d}T{mins // 60:02d}:{mins % 60:02d}:00+05:30", "o": o,
                         "h": max(o, c) * 1.0002, "l": min(o, c) * 0.9998, "c": c, "v": 0, "oi": 0})
            p = c
    sessions = tm.sessions_from_bars(bars, "09:15")
    ctx = (sessions, tm.build_pool(sessions), 20, 35)

    async def with_history(state):
        return ctx

    monkeypatch.setattr(nodes, "_time_machine_context", with_history)

    async def down():
        return None

    monkeypatch.setattr(nodes._llm, "_resolve_healthy_url", down)  # baseline picks both sides
    payload = _payload(conf=1)
    payload["research"] = {"direction": "NEUTRAL"}
    out = await underlying_graph.ainvoke(payload)
    sides = {c["side"] for c in out["candidates"]}
    assert "CE" not in sides and "PE" in sides
    assert out["diag"]["dropped"].get("timeMachine", 0) >= 1
    pe = next(c for c in out["candidates"] if c["side"] == "PE")
    assert pe["timeMachine"]["lean"] > 0
    assert any(r.startswith("Time Machine") for r in pe["reasons"])
    assert any("from the Time Machine odds" in r for r in pe["reasons"])
