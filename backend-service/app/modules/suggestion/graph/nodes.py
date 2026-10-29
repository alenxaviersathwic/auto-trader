import asyncio
from datetime import datetime
from typing import Any

from app.core.db.session import async_session_factory
from app.core.logging.logger import logger
from app.modules.master.llm.ollama_client import OllamaClient
from app.modules.strategies.service.strategy_service import StrategyService
from app.modules.suggestion.graph.prompts import SELECT_SYSTEM_PROMPT
from app.modules.suggestion.graph.state import UnderlyingState
from app.modules.suggestion.provider.underlying_config import get_config, is_market_open
from app.modules.suggestion.provider.upstox_market_data import market_data
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

MAX_DATA_AGE_SECONDS = 120
REPRICE_TOLERANCE_PCT = 3.0  # after a slow AI step: keep a pick only if its premium moved less than this
_last_answer: dict[str, dict[str, Any]] = {}  # code -> {"hash": str, "answer": dict}
_strategy_service = StrategyService()
_llm = OllamaClient()
# One local model serves every card. The frontend iterates cards one by one, so normally only one
# call is in flight; the gate still caps it at 2 if two browser tabs (or a manual API call) overlap.
# Watch [OLLAMA_TIMING] in the logs: if load/answer times roughly double, drop this to Semaphore(1).
_ai_gate = asyncio.Semaphore(2)
AI_TIMEOUT_SECONDS = 180.0


# ───────────────────────── per-underlying nodes ─────────────────────────
async def gather(state: UnderlyingState) -> dict[str, Any]:
    """Four inputs at the same time: Upstox data, strategies, vector memory (research is already in state)."""
    code = state["code"]
    cfg = get_config(code)
    if not state["params"].get("ignoreMarketHours") and not is_market_open(cfg):  # type: ignore[arg-type]
        return {"error": f"market closed ({cfg.open}-{cfg.close} IST)", "strategies": []}  # type: ignore[union-attr]
    if cfg and not cfg.optionsSupported:
        return {
            "error": f"{code}: MCX options liquidity is too thin to trade here -- see MCX_BASEMETAL_FUT_TREND (futures-only strategy)",
            "strategies": [],
        }

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
    drop_reasons: dict[str, int] = {}
    menu = build_menu(  # type: ignore[arg-type]
        cfg, state["market"], bias, state["params"]["minProfitMargin"],
        max_margin=state["params"].get("maxProfitMargin", 10.0),
        max_stop=state["params"].get("maxStopLossPct", 5.0),
        reasons=drop_reasons,
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
        chains = state["market"].get("chains", [])
        if not chains:
            out["error"] = "no option chain returned for this underlying"
        elif not drop_reasons:
            out["error"] = "option chain had no strikes near spot"
        else:
            why = ", ".join(f"{n} {k}" for k, n in sorted(drop_reasons.items(), key=lambda x: -x[1]))
            out["error"] = f"no executable contract -- dropped: {why}"
        logger.info(f"[MENU_EMPTY] {state['code']} spot={state['market'].get('spot')} chains={len(chains)} dropped={drop_reasons}")
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
                async with _ai_gate:
                    answer = await _llm.generate_structured(
                        [{"role": "user", "content": user}],
                        AiAnswer,
                        system_prompt=SELECT_SYSTEM_PROMPT,
                        timeout=AI_TIMEOUT_SECONDS,
                        think=False,
                        num_predict=900,  # a picks JSON is a few hundred tokens; stops runaway answers
                        keep_alive="30m",  # loop calls every few minutes: never unload between them
                    )
                ids = {m["id"] for m in state["menu"]}
                if answer.picks and all(p.id in ids for p in answer.picks):
                    break
                if not answer.picks and answer.noPickReason:
                    break
                answer = None
            except Exception as e:
                logger.warning(f"suggestion AI select failed ({state['code']}): {type(e).__name__}: {e}")
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
    spot = state["market"]["spot"]
    live: dict[str, float] | None = None
    if not fresh and answer.get("picks"):
        # The AI step outlasted the freshness window: re-read prices once instead of dropping every pick.
        live, new_spot = await _live_prices(state["code"])
        if live is not None:
            fresh, spot = True, new_spot or spot
    out: list[dict[str, Any]] = []
    dropped = {"stale": 0, "priceMoved": 0, "notOnMenu": 0, "lowConfidence": 0, "strategyRule": 0, "lowEdge": 0}
    for pk in answer.get("picks", []):
        m = by_id.get(pk["id"])
        if not m:
            dropped["notOnMenu"] += 1
            continue
        if not fresh:
            dropped["stale"] += 1
            continue
        if live is not None:
            ltp = live.get(m["instrumentKey"])
            if not ltp:
                dropped["stale"] += 1
                continue
            if abs(ltp - m["entry"]) / m["entry"] * 100 > REPRICE_TOLERANCE_PCT:
                dropped["priceMoved"] += 1
                continue  # premium moved too far while the AI was thinking: the setup is gone
            m = {**m, "entry": round(ltp, 2),
                 "target": round(ltp * (1 + m["marginPct"] / 100), 2),
                 "stop": round(ltp * (1 - m["stopPct"] / 100), 2)}
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
                    "spot": spot,
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


async def _live_prices(code: str) -> tuple[dict[str, float] | None, float | None]:
    """Fresh LTP per option instrumentKey for one underlying, or (None, None) when it cannot be read."""
    try:
        cfg = get_config(code)
        async with async_session_factory() as s:
            market = await market_data.fetch(cfg, s)  # type: ignore[arg-type]
    except Exception as e:
        logger.warning(f"suggestion reprice failed ({code}): {type(e).__name__}: {e}")
        return None, None
    prices: dict[str, float] = {}
    for c in market.get("chains", []):
        for row in c["strikes"]:
            for side in ("CE", "PE"):
                if row[side]["key"] and row[side]["ltp"]:
                    prices[row[side]["key"]] = row[side]["ltp"]
    return prices, market.get("spot")
