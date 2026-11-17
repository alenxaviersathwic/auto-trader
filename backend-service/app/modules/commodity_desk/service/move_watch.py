"""
The news sub-agent for sudden moves, on EVERY scanned underlying (indices and commodities).

A move is "sudden" when the 1-minute futures / spot price travelled at least MOVE_ATR x ATR5 AND MIN_PCT[type] percent
in the last WINDOW_MIN minutes (17 Nov 2026: SENSEX fell 82,800 -> 82,578 in ~35 min with no reason shown anywhere).
Then, in the background:
  1. stores the move (market_moves, news PENDING) right away
  2. collects fresh headlines that NAME the instrument (research/service/news_service.recent_headlines)
  3. the local LLM explains the move USING ONLY those headlines -- or says plainly that no headline explains it
     (cause NO_CLEAR_NEWS: flows / technical). Without the model, the code lists the headlines and marks the cause
     UNCLEAR rather than guessing.
  4. raises a MARKET_MOVE notification and feeds the Commodity Desk's news sub-agent (recent()).
Cooldown: one report per underlying and direction every COOLDOWN_S (a move that keeps going is the same move).
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from collections import deque
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.logging.logger import logger

IST = ZoneInfo("Asia/Kolkata")
WINDOW_MIN = 15
MOVE_ATR = 2.5
MIN_PCT = {"INDEX": 0.25, "COMMODITY": 0.4}
COOLDOWN_S = 45 * 60
RECENT_S = 3 * 3600
LLM_TIMEOUT_S = 60.0

_last: dict[tuple[str, str], float] = {}
_active: dict[str, dict[str, Any]] = {}  # code -> {since, step, direction, pct}: news checks running right now
_recent: dict[str, deque] = {}
_tasks: set[asyncio.Task] = set()

SYSTEM = ("You explain sudden market moves to an Indian options trader. Use ONLY the numbered headlines given. If "
          "none of them explains the move, say so plainly (cause NO_CLEAR_NEWS: likely flows or technical selling / "
          "buying) and do not guess. 2-4 short sentences. JSON only.")
SCHEMA = {"type": "object", "properties": {
    "cause": {"type": "string", "enum": ["NEWS", "NO_CLEAR_NEWS"]},
    "summary": {"type": "string"},
    "headlineIds": {"type": "array", "items": {"type": "integer"}}},
    "required": ["cause", "summary", "headlineIds"]}


def detect(code: str, utype: str, analysis: dict[str, Any], now_mono: float | None = None) -> dict[str, Any] | None:
    """The sudden move in the last WINDOW_MIN minutes, or None. Pure apart from the cooldown memory."""
    b1 = analysis.get("bars1") or []
    atr5 = float(analysis.get("atr5") or 0.0)
    if len(b1) < WINDOW_MIN + 1 or atr5 <= 0:
        return None
    p0, p1 = float(b1[-1 - WINDOW_MIN]["c"]), float(b1[-1]["c"])
    chg = p1 - p0
    pct = chg / p0 * 100 if p0 else 0.0
    if abs(chg) < MOVE_ATR * atr5 or abs(pct) < MIN_PCT.get(utype, 0.3):
        return None
    direction = "UP" if chg > 0 else "DOWN"
    t = time.monotonic() if now_mono is None else now_mono
    if t - _last.get((code, direction), -1e9) < COOLDOWN_S:
        return None
    _last[(code, direction)] = t
    return {"code": code, "type": utype, "direction": direction, "from": p0, "to": p1, "pct": round(pct, 3),
            "atr": round(abs(chg) / atr5, 2), "windowMin": WINDOW_MIN}


def recent(code: str) -> list[dict[str, Any]]:
    """Explained moves of the last 3 hours for this underlying, newest first (for the desk's news sub-agent)."""
    q = _recent.get(code) or deque()
    cut = time.monotonic() - RECENT_S
    return [m for t, m in reversed(q) if t >= cut]


def _clean(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


async def explain(move: dict[str, Any], headlines: list[dict[str, Any]]) -> dict[str, Any]:
    """{cause, summary, used (headlines), source} -- the LLM's reading of the headlines, or the code fallback."""
    if not headlines:
        return {"cause": "NO_CLEAR_NEWS", "source": "CODE", "used": [],
                "summary": (f"No fresh headline names {move['code']} in the research feeds: the "
                            f"{move['pct']:+.2f}% move looks flow- or technically-driven so far.")}
    from app.modules.ai_master.llm.ollama_client import chat, pick_model

    listing = "\n".join(f"{i}. [{h.get('source')}] {h['title']} -- {h.get('summary', '')[:200]}"
                        for i, h in enumerate(headlines, 1))
    user = (f"{move['code']} moved {move['direction'].lower()} {move['pct']:+.2f}% "
            f"({move['from']:,.2f} -> {move['to']:,.2f}) in {move['windowMin']} minutes.\nHeadlines:\n{listing}")
    try:
        data = await chat({"model": await pick_model(fast=True), "format": SCHEMA,
                           "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                           "options": {"temperature": 0.1, "num_predict": 300}}, timeout=LLM_TIMEOUT_S)
        ans = json.loads(_clean(data.get("message", {}).get("content", "")))
        ids = [i for i in ans.get("headlineIds") or [] if isinstance(i, int) and 1 <= i <= len(headlines)]
        cause = ans.get("cause") if ans.get("cause") in ("NEWS", "NO_CLEAR_NEWS") else "NO_CLEAR_NEWS"
        if cause == "NEWS" and not ids:
            cause = "NO_CLEAR_NEWS"  # a cause must point at a headline
        return {"cause": cause, "summary": str(ans.get("summary") or "")[:800], "source": "LLM",
                "used": [headlines[i - 1] for i in ids]}
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[MOVE] {move['code']} explain failed ({type(e).__name__}: {e}); code summary")
        top = headlines[0]["title"]
        return {"cause": "UNCLEAR", "source": "CODE", "used": headlines[:3],
                "summary": (f"Headlines around the move (not checked as the cause): \"{top}\""
                            + (f" and {len(headlines) - 1} more." if len(headlines) > 1 else "."))}


async def _run(move: dict[str, Any]) -> None:
    from app.core.db.session import async_session_factory
    from app.core.events import notify as nt
    from app.modules.commodity_desk.entity.market_move_entity import MarketMove
    from app.modules.commodity_desk.repository.commodity_desk_repository import commodity_desk_repository as repo
    from app.modules.research.service import news_service

    now = datetime.now(UTC)
    row_id = None
    _active[move["code"]] = {"code": move["code"], "since": now.isoformat(), "step": "SAVING",
                             "direction": move["direction"], "pct": move["pct"]}
    try:
        async with async_session_factory() as s:
            row = await repo.save(s, MarketMove(
                underlyingCode=move["code"], underlyingType=move["type"], detectedAt=now, direction=move["direction"],
                windowMin=move["windowMin"], priceFrom=move["from"], priceTo=move["to"], movePct=move["pct"],
                moveAtr=move["atr"], newsState="PENDING", headlines=[]))
            await s.commit()
            row_id = row.id
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[MOVE] {move['code']} not saved: {type(e).__name__}: {e}")
    _active[move["code"]]["step"] = "READING_HEADLINES"
    try:
        heads = await news_service.recent_headlines(move["code"], hours=3)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[MOVE] {move['code']} headlines failed: {type(e).__name__}: {e}")
        heads = []
    _active[move["code"]].update(step="EXPLAINING" if heads else "NO_HEADLINES", headlines=len(heads))
    try:
        ex = await explain(move, heads)
    finally:
        _active.pop(move["code"], None)
    state = {"NEWS": "FOUND", "UNCLEAR": "UNCLEAR"}.get(ex["cause"], "NO_NEWS")
    if row_id:
        try:
            async with async_session_factory() as s:
                row = await repo.get_move(s, row_id)
                if row:
                    row.newsState, row.cause, row.summary = state, ex["cause"], ex["summary"]
                    row.headlines, row.source = ex["used"] or heads[:5], ex["source"]
                    await s.commit()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[MOVE] {move['code']} update failed: {type(e).__name__}: {e}")
    at = now.astimezone(IST).strftime("%H:%M")
    _recent.setdefault(move["code"], deque(maxlen=20)).append(
        (time.monotonic(), {"at": at, "direction": move["direction"], "movePct": move["pct"], "summary": ex["summary"],
                            "cause": ex["cause"]}))
    logger.info(f"[MOVE] {move['code']} {move['pct']:+.2f}% in {move['windowMin']} min -> {ex['cause']}: {ex['summary'][:160]}")
    await nt.notify(nt.MARKET_MOVE, f"{move['code']} {move['direction'].lower()} {move['pct']:+.2f}% in "
                    f"{move['windowMin']} min", ex["summary"], severity="warning" if move["direction"] == "DOWN" else "info",
                    link="/traders?tab=traders", data={"moveId": row_id, "code": move["code"], "cause": ex["cause"]})


def active() -> list[dict[str, Any]]:
    """News checks running right now (for the UI's live view)."""
    return list(_active.values())


def check(code: str, utype: str, analysis: dict[str, Any]) -> None:
    """Called on every scan: start the news sub-agent when a sudden move just happened. Never raises."""
    try:
        move = detect(code, utype, analysis)
        if move:
            t = asyncio.create_task(_run(move))
            _tasks.add(t)
            t.add_done_callback(_tasks.discard)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[MOVE] {code} check failed: {type(e).__name__}: {e}")
