import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from langgraph.graph import END
from langgraph.types import Send
from sqlalchemy import update

from app.core.db.session import async_session_factory
from app.core.logging.logger import logger
from app.modules.master.llm.ollama_client import OllamaClient
from app.modules.strategies.service.strategy_service import StrategyService
from app.modules.suggestion.entity.suggestion_entity import SuggestionRun
from app.modules.suggestion.graph.prompts import SELECT_SYSTEM_PROMPT
from app.modules.suggestion.graph.state import SuggestionState, UnderlyingState
from app.modules.suggestion.provider.underlying_config import get_config, is_market_open
from app.modules.suggestion.provider.upstox_market_data import market_data
from app.modules.suggestion.repository.suggestion_repository import (
    entity_for,
    make_ref,
    risk_level,
    suggestion_repository,
)
from app.modules.suggestion.schema.suggestion_schema import AiAnswer
from app.modules.suggestion.service import memory_service
from app.modules.suggestion.service.menu_builder import (
    baseline_pick,
    brief_hash,
    build_brief,
    build_menu,
    direction_bias,
    expected_edge_pct,
    volume_adjustment,
)
from app.modules.suggestion.service.selector import select_underlyings

MAX_DATA_AGE_SECONDS = 120
_last_answer: dict[str, dict[str, Any]] = {}  # code -> {"hash": str, "answer": dict}
_strategy_service = StrategyService()
_llm = OllamaClient()


async def _progress(run_id: int, node: str, pct: int) -> None:
    async with async_session_factory() as s:
        await s.execute(
            update(SuggestionRun).where(SuggestionRun.id == run_id).values(currentNode=node, progressPct=pct)
        )
        await s.commit()


# ───────────────────────── parent graph nodes ─────────────────────────
async def load_research(state: SuggestionState) -> dict[str, Any]:
    """Step 1: does Research have data? Pick top INDEX + top COMMODITY underlyings from it."""
    p = state["params"]
    await _progress(state["runId"], "load_research", 5)
    async with async_session_factory() as s:
        sel = await select_underlyings(s, p["indexCount"], p["commodityCount"], p.get("only"))
    chosen, run_id = sel["items"], sel["runId"]
    if run_id is None:
        return {"status": "NO_RESEARCH", "underlyings": []}
    return {
        "status": "OK" if chosen else "NO_UNDERLYINGS",
        "underlyings": chosen,
        "researchRunId": run_id,
    }


def route_after_research(state: SuggestionState):
    """Conditional edge + parallel fan-out: one branch per underlying, run at the same time."""
    if state.get("status") != "OK":
        return END
    return [
        Send("analyze_underlying", {"runId": state["runId"], "params": state["params"], "research": u,
                                    "code": u["underlyingCode"]})
        for u in state["underlyings"]
    ]


async def analyze_underlying(payload: dict[str, Any]) -> dict[str, Any]:
    from app.modules.suggestion.graph.builder import underlying_graph

    out: UnderlyingState = await underlying_graph.ainvoke(payload)
    prices: dict[str, float] = {}
    for c in (out.get("market") or {}).get("chains", []):
        for row in c["strikes"]:
            for side in ("CE", "PE"):
                if row[side]["key"]:
                    prices[row[side]["key"]] = row[side]["ltp"]
    update_: dict[str, Any] = {"results": out.get("candidates", []), "prices": prices,
                               "iterated": {payload["code"]: datetime.now(UTC).isoformat()},
                               "notes": {payload["code"]: out.get("error") or out.get("note") or ""},
                               "aiUsed": 0 if out.get("usedBaseline") or out.get("error") else 1,
                               "baselineUsed": 1 if out.get("usedBaseline") else 0}
    if out.get("error"):
        update_["skipped"] = [{"underlying": payload["code"], "reason": out["error"]}]
    return update_


async def pick_top(state: SuggestionState) -> dict[str, Any]:
    """Rank by confidence, max N total, max per underlying, linked indices count as one group."""
    p = state["params"]
    await _progress(state["runId"], "pick_top", 80)
    per_group: dict[str, int] = {}
    picks: list[dict[str, Any]] = []
    for c in sorted(state.get("results", []), key=lambda c: (c.get("edge", 0), c["confidence"]), reverse=True):
        cfg = get_config(c["underlyingCode"])
        group = (cfg.linkedGroup if cfg and cfg.linkedGroup else c["underlyingCode"]) if cfg else c["underlyingCode"]
        if per_group.get(group, 0) >= p["maxPerUnderlying"]:
            continue
        per_group[group] = per_group.get(group, 0) + 1
        picks.append(c)
        if len(picks) >= p["maxSuggestions"]:
            break
    for i, c in enumerate(picks, 1):
        c["rank"] = i
    return {"picks": picks}


async def save_picks(state: SuggestionState) -> dict[str, Any]:
    await _progress(state["runId"], "save", 88)
    now = datetime.now(UTC)
    valid_until = now + timedelta(minutes=state["params"].get("validMinutes", 15))
    by_code: dict[str, list[dict[str, Any]]] = {}
    for c in state.get("picks", []):
        by_code.setdefault(c["underlyingCode"], []).append(c)
    ids: list[int] = []
    async with async_session_factory() as s:
        # Every analysed underlying replaces its own "latest" set, even when it has no picks now.
        for code in {u["underlyingCode"] for u in state.get("underlyings", [])} | set(by_code):
            ent = entity_for(code)
            rows = []
            for c in by_code.get(code, []):
                rows.append(
                    ent(
                        runId=state["runId"], ref=make_ref(code, state["runId"], c["rank"], now),
                        underlyingCode=code, underlyingType=c["underlyingType"], contractId=c["id"],
                        instrumentKey=c.get("instrumentKey"), optionType=c["side"], spot=c.get("spot", 0),
                        strike=c["strike"], expiry=c["expiry"], entry=c["entry"], stop=c["stop"],
                        target=c["target"], profitMarginPct=c["marginPct"], rewardRisk=c["rewardRisk"],
                        confidence=c["confidence"],
                        riskLevel=risk_level(c["confidence"], c["rewardRisk"], c.get("spreadPct", 0)),
                        rank=c["rank"], strategy=c.get("strategy"), reasons=c.get("reasons", []),
                        risks=c.get("risks", []), source=c["source"], validUntil=valid_until, isLatest=True,
                    )
                )
            await suggestion_repository.replace_latest(s, code, rows)
            for row, c in zip(rows, by_code.get(code, []), strict=True):
                ids.append(row.id)
                await memory_service.remember_pending(s, row, c.get("bias", "NEUTRAL"), "UNKNOWN")
        await s.commit()
    return {"savedIds": ids}


async def track_outcomes(state: SuggestionState) -> dict[str, Any]:
    await _progress(state["runId"], "track_outcomes", 95)
    async with async_session_factory() as s:
        n = await memory_service.resolve_outcomes(s, state.get("prices", {}))
        await s.commit()
    return {"outcomesResolved": n}


# ───────────────────────── per-underlying nodes ─────────────────────────
async def gather(state: UnderlyingState) -> dict[str, Any]:
    """Four inputs at the same time: Upstox data, strategies, vector memory (research is already in state)."""
    code = state["code"]
    cfg = get_config(code)
    if not state["params"].get("ignoreMarketHours") and not is_market_open(cfg):  # type: ignore[arg-type]
        return {"error": f"market closed ({cfg.open}-{cfg.close} IST)", "strategies": []}  # type: ignore[union-attr]

    async def get_market():
        async with async_session_factory() as s:
            return await market_data.fetch(cfg, s)  # type: ignore[arg-type]

    async def get_strategies():
        try:
            async with async_session_factory() as s:
                items = await _strategy_service.list_suggestable_summaries(
                    s, market="OPTIONS", underlying_type=cfg.type  # type: ignore[union-attr]
                )
            return items[:8]
        except Exception as e:  # strategies are helpful, not required
            logger.warning(f"suggestion strategies unavailable: {e}")
            return []

    market, strategies = await asyncio.gather(get_market(), get_strategies(), return_exceptions=True)
    if isinstance(market, BaseException):
        return {"error": f"market data: {market}", "strategies": []}
    items = [] if isinstance(strategies, BaseException) else strategies
    lines = [
        f"{i['name']} [trend={i.get('bias') or 'ANY'}, side={i.get('optionSide') or 'ANY'}]: {i.get('description', '')}"
        for i in items
    ]
    return {"market": market, "strategies": lines, "strategyNames": [i["name"] for i in items]}


async def make_menu(state: UnderlyingState) -> dict[str, Any]:
    cfg = get_config(state["code"])
    bias = direction_bias(state["research"], state["market"])
    brief = build_brief(cfg, state["research"], state["market"], bias)  # type: ignore[arg-type]
    menu = build_menu(  # type: ignore[arg-type]
        cfg, state["market"], bias, state["params"]["minProfitMargin"],
        max_margin=state["params"].get("maxProfitMargin", 10.0),
        max_stop=state["params"].get("maxStopLossPct", 5.0),
    )
    for m in menu:
        m["underlyingType"] = cfg.type  # type: ignore[union-attr]
    h = brief_hash(brief)
    cached = _last_answer.get(state["code"])
    reused = bool(cached and cached["hash"] == h)
    async with async_session_factory() as s:
        memory = await memory_service.recall(s, state["code"], bias, str(brief)) if not reused else []
        hits = await memory_service.hit_rate(s, state["code"])
    out: dict[str, Any] = {"bias": bias, "brief": brief, "briefHash": h, "menu": menu, "reused": reused,
                           "memory": memory, "hitRate": hits}
    if not menu:
        out["error"] = "no executable contract passed the filters (liquidity, spread, reward/risk, profit margin)"
    return out


def route_after_menu(state: UnderlyingState) -> str:
    if state.get("error"):
        return "end"
    return "validate" if state.get("reused") else "ai_select"


async def ai_select(state: UnderlyingState) -> dict[str, Any]:
    user = (
        f"BRIEF:\n{state['brief']}\n\nSTRATEGY RULES:\n{state.get('strategies') or 'none'}\n\n"
        f"PAST HIT RATE (target hit before stop, this underlying): {state.get('hitRate')}\n\n"
        f"SIMILAR PAST CASES:\n{state.get('memory') or 'none'}\n\nMENU:\n{state['menu']}"
    )
    answer = None
    if await _llm._resolve_healthy_url():
        for _ in range(2):  # one retry
            try:
                answer = await _llm.generate_structured(
                    [{"role": "user", "content": user}], AiAnswer, system_prompt=SELECT_SYSTEM_PROMPT
                )
                ids = {m["id"] for m in state["menu"]}
                if answer.picks and all(p.id in ids for p in answer.picks):
                    break
                if not answer.picks and answer.noPickReason:
                    break
                answer = None
            except Exception as e:
                logger.warning(f"suggestion AI select failed: {e}")
                answer = None
    if answer is None:
        return {"answer": {"picks": baseline_pick(state["menu"], state["bias"])}, "usedBaseline": True}
    dumped = answer.model_dump()
    _last_answer[state["code"]] = {"hash": state["briefHash"], "answer": dumped}
    return {"answer": dumped}


async def validate(state: UnderlyingState) -> dict[str, Any]:
    """Code checks every AI pick: id on menu, fresh data, volume, confidence and margin thresholds."""
    p = state["params"]
    answer = state.get("answer") or _last_answer.get(state["code"], {}).get("answer", {"picks": []})
    by_id = {m["id"]: m for m in state["menu"]}
    fetched = datetime.fromisoformat(state["market"]["fetchedAt"])
    fresh = (datetime.utcnow() - fetched).total_seconds() <= MAX_DATA_AGE_SECONDS
    candles = state["market"].get("candles") or {}
    out: list[dict[str, Any]] = []
    dropped = {"stale": 0, "notOnMenu": 0, "lowConfidence": 0, "strategyRule": 0, "lowEdge": 0}
    for pk in answer.get("picks", []):
        m = by_id.get(pk["id"])
        if not m:
            dropped["notOnMenu"] += 1
            continue
        if not fresh:
            dropped["stale"] += 1
            continue
        reasons = list(pk.get("reasons", []))
        conf = int(pk["confidence"])
        if not state.get("usedBaseline"):  # baseline ranking already counts volume
            adj = volume_adjustment(candles, m["side"])
            if adj:
                conf = max(1, min(99, conf + adj))
                ratio = candles.get("volumeRatio", 0)
                reasons.append(
                    f"Volume {ratio:.1f}x average " + ("confirms the move" if adj > 0 else "is thin, confidence reduced")
                )
        if conf < p["confidenceWanted"] or m["marginPct"] < p["minProfitMargin"]:
            dropped["lowConfidence"] += 1
            continue
        edge = expected_edge_pct(conf, m["marginPct"], m["stopPct"])
        if edge <= 0:
            dropped["lowEdge"] += 1
            continue  # at this confidence the trade does not make money on average
        reasons.append(f"Expected edge {edge:+.1f}% per trade (target +{m['marginPct']}%, stop -{m['stopPct']}%)")
        risks = list(pk.get("risks", []))
        if not m.get("withTrend", True):
            names = [n.lower() for n in state.get("strategyNames", [])]
            cited = (pk.get("strategy") or "").lower()
            if names and not any(n in cited or cited in n for n in names if cited):
                dropped["strategyRule"] += 1
                continue  # against-trend pick must cite one of the listed strategies
            if not names and conf < p["confidenceWanted"] + 10:
                dropped["strategyRule"] += 1
                continue  # no strategies to justify it: needs extra confidence
            risks.insert(0, f"Against the {state['bias'].lower()} trend")
        out.append({**m, "underlyingCode": state["code"], "confidence": conf,
                    "strategy": pk.get("strategy"), "reasons": reasons,
                    "risks": risks, "bias": state["bias"], "edge": edge,
                    "spot": state["market"]["spot"],
                    "source": "BASELINE" if state.get("usedBaseline") else "AI"})
    total = len(answer.get("picks", []))
    if out:
        note = f"{len(out)} suggestion(s) from {total} AI pick(s)"
    elif total == 0:
        note = answer.get("noPickReason") or "AI found no good contract on the menu"
    else:
        why = ", ".join(f"{n} {k}" for k, n in dropped.items() if n)
        note = f"{total} pick(s) rejected by checks ({why}); confidence needed {p['confidenceWanted']}"
    return {"candidates": out, "note": note}
