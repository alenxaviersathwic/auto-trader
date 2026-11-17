"""
The Commodity Desk (trader COMMODITY_DESK_TRADER): specialist sub-agents + a head trader, for MCX crude oil, natural
gas, gold and silver. It runs inside every commodity scan (opportunity_finder/graph/nodes.py -> run()).

  sub-agents (code, instant):  agents/session_clock, agents/structure_agent, agents/options_agent, agents/news_agent
  risk gate  (code, final say): agents/risk_agent -- refuses before the head trader sees a setup and after it answers
  head trader (local LLM):     head_trader.decide -- reads the reports, writes its reasoning, TAKE one setup or WAIT

A scan runs every ~20 s; the model needs 5-30 s. So the head trader thinks in the BACKGROUND, and a TAKE is acted on
at the next scan only if the setup still holds: price within RECHECK_ATR of the planned entry, the risk gate still
allows it, and the decision is younger than TAKE_TTL_S. Then the setup goes into the normal opportunity flow
(contract choice, liquidity / spread / delta checks, Time Machine, edge after charges) and on to the COMMODITY
sessions that use this finder. Like every finder it follows the session's own Upstox switch.

The head trader is asked again when the setups on the table change, and otherwise every NOTE_INTERVAL_S so the desk
always shows what it is thinking. Every decision is stored (commodity_desk_decisions) with all reports.
"""
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.db.session import async_session_factory
from app.core.logging.logger import logger
from app.modules.commodity_desk.entity.desk_decision_entity import DeskDecision
from app.modules.commodity_desk.repository.commodity_desk_repository import commodity_desk_repository as repo
from app.modules.commodity_desk.service import head_trader, move_watch
from app.modules.commodity_desk.service.agents import news_agent, options_agent, risk_agent, session_clock, structure_agent

IST = ZoneInfo("Asia/Kolkata")
CODES = ("CRUDEOIL", "NATURALGAS", "GOLD", "SILVER")
NOTE_INTERVAL_S = 600.0
RESEARCH_TTL_S = 300.0
TAKE_TTL_S = 180.0
RECHECK_ATR = 0.3


class _State:
    def __init__(self) -> None:
        self.keys: frozenset = frozenset()
        self.asked_at = 0.0
        self.task: asyncio.Task | None = None
        self.approved: dict[str, Any] | None = None
        self.research: tuple[float, dict[str, Any] | None] = (0.0, None)
        # live status for the UI (live()): what ran, when, and whether the head trader is thinking right now
        self.pass_at: datetime | None = None
        self.pass_no = 0
        self.pass_ms = 0.0
        self.stances: dict[str, str] = {}
        self.allowed = 0
        self.refused = 0
        self.thinking_since: datetime | None = None
        self.decided_at: datetime | None = None
        self.last_decision: str | None = None
        self.sent_at: datetime | None = None


_state: dict[str, _State] = {}
_tasks: set[asyncio.Task] = set()


def _key(c: dict[str, Any]) -> tuple:
    return (c["name"], c["side"], round(float(c["entry"]), 0))


async def _research(code: str, st: _State) -> dict[str, Any] | None:
    if time.monotonic() - st.research[0] < RESEARCH_TTL_S:
        return st.research[1]
    from app.modules.research.service import news_service

    try:
        async with async_session_factory() as s:
            view = await news_service.latest_view(s, code)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[DESK] {code} research read failed: {type(e).__name__}: {e}")
        view = st.research[1]
    st.research = (time.monotonic(), view)
    return view


def reports_for(code: str, analysis: dict[str, Any], market: dict[str, Any], research: dict[str, Any] | None,
                now: datetime) -> dict[str, dict[str, Any]]:
    atr5 = float(analysis.get("atr5") or 0.0)
    return {
        "clock": session_clock.read(code, now, analysis.get("dte")),
        "structure": structure_agent.read(analysis),
        "options": options_agent.read(market, atr5, now),
        "news": news_agent.read(research, move_watch.recent(code), now),
    }


def screen(reports: dict[str, dict[str, Any]], spot: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(allowed, refused) setups after the risk gate; each carries its refusals / warnings."""
    allowed, refused = [], []
    for c in reports["structure"].get("candidates", []):
        ok, no, warn = risk_agent.check(c, reports, spot)
        c = {**c, "refusals": no, "warnings": warn}
        (allowed if ok else refused).append(c)
    return allowed, refused


def to_setup(c: dict[str, Any], d: dict[str, Any], decision_id: int | None) -> dict[str, Any]:
    """The desk's TAKE in the shape the opportunity engine's menu builder expects (opportunity_finder/service/setups)."""
    return {"name": c["name"], "side": c["side"], "strength": 4 if d["conviction"] >= 75 else 3,
            "reason": f"Commodity Desk head trader ({d['source']}, conviction {d['conviction']}): {d['thinking'][:300]}",
            "entry": c["entry"], "stop": c["stop"], "target": c["target"], "targetLevel": "desk plan (2R / structure)",
            "rr": c["rr"], "family": c.get("family", "TREND"), "withTrend": bool(c.get("withStructure")),
            "conflict": None, "deskDecisionId": decision_id}


def _compact(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for k, r in reports.items():
        data = dict(r.get("data") or {})
        data.pop("research", None)
        out[k] = {"name": r.get("name"), "stance": r.get("stance"), "score": r.get("score"),
                  "summary": r.get("summary"), "facts": r.get("facts", [])[:8], "data": data}
    return out


async def _decide(code: str, reports: dict[str, dict[str, Any]], allowed: list[dict[str, Any]],
                  refused: list[dict[str, Any]], spot: float, st: _State) -> None:
    st.thinking_since = datetime.now(UTC)
    try:
        d = await head_trader.decide(code, reports, allowed, refused)
    finally:
        st.thinking_since = None
    st.decided_at, st.last_decision = datetime.now(UTC), d["decision"]
    chosen = next((c for c in allowed if c["id"] == d.get("candidateId")), None) if d["decision"] == "TAKE" else None
    row = DeskDecision(underlyingCode=code, decidedAt=datetime.now(UTC), phase=reports["clock"]["data"]["phase"],
                       spot=spot, decision=d["decision"], source=d["source"],
                       setupName=chosen["name"] if chosen else None, side=chosen["side"] if chosen else None,
                       conviction=d["conviction"], thinking=d["thinking"], watchFor=d["watchFor"],
                       agents=_compact(reports), candidates=allowed + refused, chosen=chosen)
    try:
        async with async_session_factory() as s:
            await repo.save(s, row)
            await s.commit()
    except Exception as e:  # noqa: BLE001 -- a lost log line must not lose the decision
        logger.warning(f"[DESK] {code} decision not saved: {type(e).__name__}: {e}")
    if chosen:
        st.approved = {"candidate": chosen, "decision": d, "id": row.id, "at": time.monotonic()}
    logger.info(f"[DESK] {code} {d['decision']} ({d['source']}, conviction {d['conviction']})"
                + (f" {chosen['name']} {chosen['side']} @ {chosen['entry']}" if chosen else "") + f": {d['thinking'][:160]}")


async def _mark(decision_id: int | None, outcome: str) -> None:
    if not decision_id:
        return
    try:
        async with async_session_factory() as s:
            row = await repo.get_decision(s, decision_id)
            if row:
                row.outcome = outcome[:200]
                await s.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[DESK] outcome not saved for decision {decision_id}: {type(e).__name__}: {e}")


def _spawn(coro: Any) -> asyncio.Task:
    t = asyncio.create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
    return t


async def run(code: str, analysis: dict[str, Any], market: dict[str, Any],
              now: datetime | None = None) -> list[dict[str, Any]]:
    """One desk pass for one commodity. Returns the desk setups to trade NOW (a held TAKE), usually []."""
    if code not in CODES:
        return []
    now = now or datetime.now(IST)
    st = _state.setdefault(code, _State())
    t0 = time.perf_counter()
    spot = float(analysis.get("spot") or market.get("spot") or 0)
    atr5 = float(analysis.get("atr5") or 0.0)
    reports = reports_for(code, analysis, market, await _research(code, st), now)
    allowed, refused = screen(reports, spot)
    out: list[dict[str, Any]] = []
    st.pass_at, st.pass_no = datetime.now(UTC), st.pass_no + 1
    st.stances = {k: r.get("stance", "NEUTRAL") for k, r in reports.items()}
    st.allowed, st.refused = len(allowed), len(refused)

    ap = st.approved
    if ap:
        st.approved = None
        c = ap["candidate"]
        still = next((x for x in allowed if (x["name"], x["side"]) == (c["name"], c["side"])), None)
        age = time.monotonic() - ap["at"]
        drift = abs(spot - float(c["entry"])) / atr5 if atr5 else 99
        if age > TAKE_TTL_S:
            _spawn(_mark(ap["id"], f"not traded: decision {age:.0f}s old by the next scan"))
        elif drift > RECHECK_ATR:
            _spawn(_mark(ap["id"], f"not traded: price moved {drift:.1f} ATR from the planned entry"))
        elif not still:
            _spawn(_mark(ap["id"], "not traded: the setup no longer passes the risk gate"))
        else:
            out.append(to_setup(still, ap["decision"], ap["id"]))
            st.sent_at = datetime.now(UTC)
            _spawn(_mark(ap["id"], f"sent to the opportunity engine at {now.astimezone(IST):%H:%M:%S} IST"))

    keys = frozenset(_key(c) for c in allowed)
    due = (keys and keys != st.keys) or time.monotonic() - st.asked_at >= NOTE_INTERVAL_S
    if due and not (st.task and not st.task.done()):
        st.keys, st.asked_at = keys, time.monotonic()
        st.task = _spawn(_decide(code, reports, allowed, refused, spot, st))
    st.pass_ms = (time.perf_counter() - t0) * 1000
    return out


def _iso(t: datetime | None) -> str | None:
    return t.isoformat() if t else None


def live() -> list[dict[str, Any]]:
    """What each commodity's desk is doing right now (in-memory, this process): the last pass of the sub-agents, the
    risk gate's count, and whether the head trader is thinking. Nothing here is estimated: an idle desk shows idle."""
    return [{"code": code, "passAt": _iso(st.pass_at), "passNo": st.pass_no, "passMs": round(st.pass_ms, 1),
             "stances": st.stances, "allowed": st.allowed, "refused": st.refused,
             "thinkingSince": _iso(st.thinking_since), "decidedAt": _iso(st.decided_at),
             "lastDecision": st.last_decision, "sentAt": _iso(st.sent_at)}
            for code, st in sorted(_state.items())]
