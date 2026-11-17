"""Commodity Desk (17 Nov 2026): sub-agents, risk gate, head-trader checks, the hold-at-next-scan rule, the sudden-move
news sub-agent and the never-real-money guard. Pure functions + monkeypatched model; no DB, no network."""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.modules.commodity_desk.service import desk_service, head_trader, move_watch
from app.modules.commodity_desk.service.agents import news_agent, options_agent, risk_agent, session_clock, structure_agent
from app.modules.trade_history.service import trader_presets as tp

IST = ZoneInfo("Asia/Kolkata")


def _ist(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=IST)


# ───────── session clock ─────────
def test_clock_eia_crude_follows_us_daylight_saving():
    # Wed 18 Nov 2026 (US standard time): EIA 10:30 ET = 21:00 IST
    r = session_clock.read("CRUDEOIL", _ist(2026, 11, 18, 20, 45))
    assert r["stance"] == "CAUTION" and r["data"]["event"]["at"] == "21:00"
    r = session_clock.read("CRUDEOIL", _ist(2026, 11, 18, 20, 55))
    assert r["stance"] == "BLOCK"
    # Wed 15 Jul 2026 (US daylight time): EIA = 20:00 IST
    r = session_clock.read("CRUDEOIL", _ist(2026, 7, 15, 19, 52))
    assert r["stance"] == "BLOCK" and r["data"]["event"]["at"] == "20:00"
    # natural gas has its own day (Thursday); a Wednesday evening is clear for it
    assert session_clock.read("NATURALGAS", _ist(2026, 11, 18, 20, 55))["stance"] == "NEUTRAL"


def test_clock_phases_and_closing():
    assert session_clock.phase(_ist(2026, 11, 17, 10, 0)) == "ASIA"
    assert session_clock.phase(_ist(2026, 11, 17, 15, 0)) == "EUROPE"  # London opened 13:30 IST in winter
    assert session_clock.phase(_ist(2026, 11, 17, 20, 0)) == "US_OPEN"  # NY 08:30 = 19:00 IST
    assert session_clock.phase(_ist(2026, 11, 17, 23, 5)) == "CLOSING"  # winter close 23:30
    assert session_clock.read("GOLD", _ist(2026, 11, 17, 23, 10))["stance"] == "BLOCK"


# ───────── price structure ─────────
def _bars(closes, wick=2.0, t0=0, step=5):
    out, prev = [], closes[0]
    for i, c in enumerate(closes):
        out.append({"t": f"2026-11-17T{(9 * 60 + t0 + i * step) // 60:02d}:{(9 * 60 + t0 + i * step) % 60:02d}:00+05:30",
                    "o": prev, "h": max(prev, c) + wick, "l": min(prev, c) - wick, "c": c})
        prev = c
    return out


def _uptrend_pullback():
    b5 = _bars([8000 + i * 6 for i in range(20)] + [8114, 8104, 8098])  # rally, then 3 bars down into the value zone
    b1 = _bars([8100 + (i % 3) for i in range(14)] + [8096, 8099.5, 8106], wick=0.5, step=1)
    return {"bars5": b5, "bars1": b1, "atr5": 10.0, "trend15": "UP", "trend5": "UP",
            "ema5": {"ema9": 8100.0, "ema20": 8094.0, "ema21": 8092.0},
            "vwap": {"value": 8090.0, "above": True, "distPct": 0.2}, "levels": {"dayHigh": 8130.0}, "spot": 8106}


def test_structure_finds_a_trend_pullback_with_a_1m_trigger():
    r = structure_agent.read(_uptrend_pullback())
    pb = [c for c in r["candidates"] if c["name"] == "DESK_TREND_PULLBACK"]
    assert r["stance"] == "BULLISH" and pb and pb[0]["side"] == "CE"
    c = pb[0]
    assert c["stop"] < c["entry"] < c["target"] and c["rr"] >= structure_agent.MIN_RR and c["withStructure"]


def test_structure_no_pullback_without_the_1m_trigger():
    a = _uptrend_pullback()
    a["bars1"][-1] = {**a["bars1"][-1], "c": 8095.0}  # 1-minute bar still falling
    assert not [c for c in structure_agent.read(a)["candidates"] if c["name"] == "DESK_TREND_PULLBACK"]


def test_structure_breakout_must_be_fresh_and_not_chased():
    b5 = _bars([8000 + (i % 4) * 3 for i in range(14)] + [8030])  # range 8000-8011, then a strong break
    b5[-1] = {**b5[-1], "o": 8008, "l": 8007, "h": 8031, "c": 8030}
    a = {"bars5": b5, "bars1": _bars([8020], step=1), "atr5": 15.0, "trend15": "FLAT", "trend5": "UP", "levels": {}}
    r = structure_agent.read(a)
    br = [c for c in r["candidates"] if c["name"] == "DESK_RANGE_BREAK"]
    assert br and br[0]["side"] == "CE"
    a["bars1"] = _bars([8040], step=1)  # 2 ATR past the level: chasing
    assert not [c for c in structure_agent.read(a)["candidates"] if c["name"] == "DESK_RANGE_BREAK"]


# ───────── option chain ─────────
def _leg(bid, ask, oi=1000, q=50):
    return {"key": "k", "ltp": (bid + ask) / 2, "oi": oi, "volume": 10, "bid": bid, "ask": ask, "delta": 0.5, "iv": 30,
            "bidQty": q, "askQty": q}


def _market(today="2026-11-17"):
    strikes = [{"strike": s, "CE": _leg(99, 101, oi=5000 if s == 8150 else 1000), "PE": _leg(99, 101, oi=4000 if s == 8000 else 900)}
               for s in (8000, 8050, 8100, 8150, 8200)]
    return {"spot": 8100.0, "chains": [
        {"expiry": today, "spot": 8100.0, "pcr": 0.9, "resistance": 8150, "support": 8000, "strikes": strikes},
        {"expiry": "2026-12-16", "spot": 8140.0, "pcr": 1.4, "resistance": 8200, "support": 8050, "strikes": strikes}]}


def test_options_reads_the_non_expiring_chain_and_its_own_future():
    r = options_agent.read(_market(), 10.0, _ist(2026, 11, 17, 18, 0))
    assert r["data"]["expiry"] == "2026-12-16" and r["data"]["chainSpot"] == 8140.0 and r["stance"] == "BULLISH"
    # a wall on the next-month chain is translated onto the front future (spread +40) before the path check
    c = {"side": "CE", "entry": 8100.0, "target": 8200.0}
    assert options_agent.path_note(c, r, 8100.0) is None  # 8200 - 40 = 8160: exactly at 60% of the path, not inside it
    c = {"side": "CE", "entry": 8100.0, "target": 8300.0}
    assert "call-OI wall 8200" in options_agent.path_note(c, r, 8100.0)


def test_options_blocks_when_atm_is_illiquid():
    m = _market()
    for ch in m["chains"]:
        for s in ch["strikes"]:
            s["CE"], s["PE"] = _leg(80, 120), _leg(80, 120)  # 40% spreads
    assert options_agent.read(m, 10.0, _ist(2026, 11, 17, 18, 0))["stance"] == "BLOCK"


# ───────── news ─────────
def test_news_needs_a_real_research_score_to_vote():
    assert news_agent.read({"direction": "BEARISH", "score": 8.9, "newsStatus": "HAS_NEGATIVE"})["score"] == 0
    assert news_agent.read({"direction": "BEARISH", "score": 40, "newsStatus": "HAS_NEGATIVE"})["stance"] == "BEARISH"
    assert "no Research Engine read" in news_agent.read(None)["summary"]


# ───────── risk gate ─────────
def _reports(clock="NEUTRAL", struct=2):
    return {"clock": {"stance": clock, "summary": "x"}, "structure": {"score": struct},
            "options": options_agent.read(_market(), 10.0, _ist(2026, 11, 17, 18, 0))}


def test_risk_gate_refuses_clock_block_and_counter_structure():
    c = {"side": "CE", "entry": 8100.0, "stop": 8090.0, "target": 8130.0, "rr": 3.0}
    assert risk_agent.check(c, _reports(), 8100.0)[0]
    ok, no, _ = risk_agent.check(c, _reports(clock="BLOCK"), 8100.0)
    assert not ok and no
    ok, no, _ = risk_agent.check(c, _reports(struct=-3), 8100.0)
    assert not ok and "other way" in no[0]
    ok, no, _ = risk_agent.check({**c, "rr": 1.2}, _reports(), 8100.0)
    assert not ok


# ───────── head trader ─────────
def _allowed():
    return [{"id": "c1", "name": "DESK_TREND_PULLBACK", "side": "CE", "entry": 8106.0, "stop": 8094.0, "target": 8130.0,
             "rr": 2.0, "why": "w", "withStructure": True, "warnings": [], "refusals": []}]


def _patch_model(monkeypatch, answer: str):
    from app.modules.ai_master.llm import ollama_client

    async def fake_chat(payload, timeout, cache_ttl=0.0):
        return {"message": {"content": answer}}

    async def fake_pick(fast=False, requested=None):
        return "qwen3:8b"

    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    monkeypatch.setattr(ollama_client, "pick_model", fake_pick)


def test_head_trader_take_must_name_an_allowed_setup(monkeypatch):
    _patch_model(monkeypatch, '{"decision":"TAKE","candidateId":"c9","conviction":80,"thinking":"t","watchFor":"w"}')
    d = asyncio.run(head_trader.decide("CRUDEOIL", {"structure": {}}, _allowed(), []))
    assert d["decision"] == "WAIT" and d["source"] == "LLM"


def test_head_trader_low_conviction_is_a_wait(monkeypatch):
    _patch_model(monkeypatch, '{"decision":"TAKE","candidateId":"c1","conviction":40,"thinking":"t","watchFor":"w"}')
    assert asyncio.run(head_trader.decide("CRUDEOIL", {"structure": {}}, _allowed(), []))["decision"] == "WAIT"
    _patch_model(monkeypatch, '{"decision":"TAKE","candidateId":"c1","conviction":72,"thinking":"t","watchFor":"w"}')
    d = asyncio.run(head_trader.decide("CRUDEOIL", {"structure": {}}, _allowed(), []))
    assert d["decision"] == "TAKE" and d["candidateId"] == "c1"


def test_head_trader_falls_back_to_code_when_the_model_fails(monkeypatch):
    _patch_model(monkeypatch, "not json")
    d = asyncio.run(head_trader.decide("CRUDEOIL", {"structure": {"stance": "BULLISH"}}, _allowed(), []))
    assert d["source"] == "CODE" and d["decision"] == "TAKE" and "Model unavailable" in d["thinking"]


# ───────── hold at the next scan ─────────
def test_desk_trades_a_take_only_if_it_still_holds(monkeypatch):
    a = _uptrend_pullback()
    st = desk_service._State()
    st.research = (1e18, None)
    monkeypatch.setitem(desk_service._state, "CRUDEOIL", st)
    monkeypatch.setattr(desk_service, "_spawn", lambda coro: coro.close())  # no background work in the test
    now = _ist(2026, 11, 17, 18, 0)
    reports = desk_service.reports_for("CRUDEOIL", a, _market(), None, now)
    allowed, _ = desk_service.screen(reports, 8106.0)
    c = next(x for x in allowed if x["name"] == "DESK_TREND_PULLBACK")
    d = {"decision": "TAKE", "conviction": 70, "source": "LLM", "thinking": "agree", "watchFor": "w"}
    st.approved = {"candidate": c, "decision": d, "id": 1, "at": desk_service.time.monotonic()}
    out = asyncio.run(desk_service.run("CRUDEOIL", a, _market(), now))
    assert len(out) == 1 and out[0]["name"] == "DESK_TREND_PULLBACK" and out[0]["deskDecisionId"] == 1
    assert tp.assign_trader_for_opportunity(out[0]["name"]) == "COMMODITY_DESK_TRADER"
    live = {x["code"]: x for x in desk_service.live()}["CRUDEOIL"]
    assert live["passAt"] and live["stances"]["structure"] == "BULLISH" and live["sentAt"] and live["thinkingSince"] is None
    # same TAKE, but price ran 2 ATR away before the next scan: not traded
    st.approved = {"candidate": {**c, "entry": c["entry"] - 20}, "decision": d, "id": 2, "at": desk_service.time.monotonic()}
    assert asyncio.run(desk_service.run("CRUDEOIL", a, _market(), now)) == []


# ───────── sudden-move news sub-agent ─────────
def test_move_watch_detects_once_per_direction():
    move_watch._last.clear()
    b1 = _bars([82800 - i * 15 for i in range(16)], wick=1, step=1)  # -225 pts in 15 min
    a = {"bars1": b1, "atr5": 50.0}
    m = move_watch.detect("SENSEX", "INDEX", a, now_mono=1000.0)
    assert m and m["direction"] == "DOWN" and m["atr"] >= move_watch.MOVE_ATR
    assert move_watch.detect("SENSEX", "INDEX", a, now_mono=1500.0) is None  # cooldown
    assert move_watch.detect("SENSEX", "INDEX", {"bars1": b1, "atr5": 200.0}, now_mono=9000.0) is None  # small vs ATR


def test_move_explanation_never_invents_a_cause(monkeypatch):
    move = {"code": "CRUDEOIL", "direction": "DOWN", "pct": -0.6, "from": 8100.0, "to": 8051.0, "windowMin": 15}
    ex = asyncio.run(move_watch.explain(move, []))
    assert ex["cause"] == "NO_CLEAR_NEWS" and ex["source"] == "CODE"
    _patch_model(monkeypatch, '{"cause":"NEWS","summary":"s","headlineIds":[]}')  # a cause with no headline
    heads = [{"title": "OPEC+ surprise", "source": "ET"}]
    assert asyncio.run(move_watch.explain(move, heads))["cause"] == "NO_CLEAR_NEWS"
    _patch_model(monkeypatch, '{"cause":"NEWS","summary":"OPEC+","headlineIds":[1]}')
    ex = asyncio.run(move_watch.explain(move, heads))
    assert ex["cause"] == "NEWS" and ex["used"] == heads


# ───────── the session's Upstox switch decides, for every finder ─────────
def test_every_finder_follows_the_session_upstox_switch():
    # 17 Nov 2026: the desk is no longer simulated-only; its picks are acted on like any other finder's
    assert tp.routes_to_broker(True, "NOISE_BREAKOUT")
    assert tp.routes_to_broker(True, "DESK_TREND_PULLBACK")
    assert not tp.routes_to_broker(False, "DESK_TREND_PULLBACK")


@pytest.mark.parametrize("code", ["NIFTY", "COPPER"])
def test_desk_only_runs_on_its_four_commodities(code):
    assert asyncio.run(desk_service.run(code, {}, {})) == []
