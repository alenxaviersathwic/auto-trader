from datetime import datetime

import pytest

from app.modules.suggestion.graph import nodes
from app.modules.suggestion.graph.builder import underlying_graph
from app.modules.suggestion.provider.underlying_config import get_config
from app.modules.suggestion.schema.suggestion_schema import AiAnswer, AiPick
from app.modules.suggestion.service.menu_builder import build_menu, direction_bias


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
    assert direction_bias({"direction": "BULLISH"}, {"candles": {"trendPct": 0.5}}) == "BULLISH"
    assert direction_bias({"direction": "BEARISH"}, {"candles": {"trendPct": -0.5}}) == "BEARISH"
    assert direction_bias({}, {"candles": {"trendPct": 0.0}}) == "NEUTRAL"


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

    monkeypatch.setattr(nodes, "async_session_factory", lambda: _Ctx())
    monkeypatch.setattr(nodes.market_data, "fetch", fake_fetch)
    async def fake_hit(*a, **k):
        return "no history yet"

    monkeypatch.setattr(nodes.memory_service, "recall", fake_recall)
    monkeypatch.setattr(nodes.memory_service, "hit_rate", fake_hit)
    monkeypatch.setattr(nodes._strategy_service, "list_suggestable_summaries", no_strats)
    nodes._last_answer.clear()


def _payload(conf=80):
    return {"runId": 1, "code": "NIFTY", "research": {"direction": "BULLISH"},
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
                               AiPick(id="NIFTY-2026-10-29-24050-CE", confidence=60)])

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
    out = await underlying_graph.ainvoke(_payload(conf=50))
    assert out["usedBaseline"] is True
    assert out["candidates"] and all(c["source"] == "BASELINE" for c in out["candidates"])


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
    assert direction_bias({"direction": "BEARISH"}, {"candles": {"trendPct": 0.5}}) == "BEARISH"
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
    assert ids == ["NIFTY-2026-10-29-24000-PE"]
    assert out["candidates"][0]["risks"][0].startswith("Against the bullish trend")


def test_volume_confirmation_and_dry_market():
    from app.modules.suggestion.service.menu_builder import volume_adjustment, volume_confirms

    up_high = {"volumeRatio": 1.8, "lastCandleUp": True}
    assert volume_confirms(up_high, "CE") and not volume_confirms(up_high, "PE")
    assert volume_adjustment(up_high, "CE") > 0
    assert volume_adjustment({"volumeRatio": 0.3, "lastCandleUp": True}, "CE") < 0
    assert volume_adjustment({"volumeRatio": 1.0, "lastCandleUp": True}, "CE") == 0


def test_market_hours_gate():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.modules.suggestion.provider.underlying_config import is_market_open

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


def test_expected_edge_needs_real_probability():
    from app.modules.suggestion.service.menu_builder import expected_edge_pct

    assert expected_edge_pct(70, 7.5, 3.75) > 3
    assert expected_edge_pct(30, 7.5, 3.75) < 0


@pytest.mark.asyncio
async def test_old_run_stats_with_plain_iso_strings_do_not_crash():
    from app.modules.suggestion.service.run_service import SuggestionRunService

    class _Run:
        stats = {"iterated": {"NIFTY": "2026-10-27T13:46:57+00:00"}, "notes": {"NIFTY": "x"}}

    class _Res:
        def scalars(self):
            return self

        def all(self):
            return [_Run()]

    class _Sess:
        async def execute(self, *_a, **_k):
            return _Res()

    svc = SuggestionRunService()
    done = await svc._last_completed(_Sess())
    assert done["NIFTY"]["at"].startswith("2026-10-27") and done["NIFTY"]["loop"] is None
