import asyncio
from datetime import datetime
from typing import Any

from app.core.db.session import async_session_factory
from app.core.logging.logger import logger
from app.modules.master.llm.ollama_client import OllamaClient
from app.modules.opportunities.graph.prompts import SELECT_SYSTEM_PROMPT
from app.modules.opportunities.graph.state import UnderlyingState
from app.modules.opportunities.provider.underlying_config import get_config, is_market_open
from app.modules.opportunities.provider.upstox_market_data import market_data
from app.modules.opportunities.schema.opportunity_schema import AiAnswer
from app.modules.opportunities.service import memory_service, setups as setup_detector
from app.modules.opportunities.service.market_analysis import analyze
from app.modules.opportunities.service.menu_builder import (
    baseline_pick,
    brief_hash,
    build_brief,
    build_menu,
    buildup_adjustment,
    direction_bias,
    expected_edge_pct,
    setup_adjustment,
    volume_adjustment,
    volume_confirms,
)
from app.modules.strategies.service.strategy_service import StrategyService

MAX_DATA_AGE_SECONDS = 120
REPRICE_TOLERANCE_PCT = 3.0  # after a slow AI step: keep a pick only if its premium moved less than this
_last_answer: dict[str, dict[str, Any]] = {}  # code -> {"hash": str, "answer": dict}
_strategy_service = StrategyService()
_llm = OllamaClient()
# One local model serves every card; the frontend iterates cards one by one. Cap overlap at 2.
_ai_gate = asyncio.Semaphore(2)
AI_TIMEOUT_SECONDS = 180.0
_MENU_FIELDS_FOR_AI = ("id", "side", "setup", "setupStrength", "withTrend", "volumeConfirmed", "strike", "expiryRank",
                       "entry", "target", "stop", "marginPct", "stopPct", "costPct", "delta", "rewardRisk", "spreadPct", "oi")


# ───────────────────────── per-underlying nodes ─────────────────────────
async def gather(state: UnderlyingState) -> dict[str, Any]:
    """Upstox data + strategies in parallel, then the code analysis (levels, VWAP, regime) and coded setups."""
    code = state["code"]
    cfg = get_config(code)
    if not state["params"].get("ignoreMarketHours") and not is_market_open(cfg):  # type: ignore[arg-type]
        return {"error": f"market closed ({cfg.open}-{cfg.close_today()} IST)", "strategies": []}  # type: ignore[union-attr]
    if cfg and not cfg.optionsSupported:
        return {"error": f"{code}: MCX options liquidity is too thin to trade here (futures-only)", "strategies": []}

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
            logger.warning(f"opportunities strategies unavailable: {e}")
            return []

    market, strategies = await asyncio.gather(get_market(), get_strategies(), return_exceptions=True)
    if isinstance(market, BaseException):
        return {"error": f"market data: {market}", "strategies": []}
    items = [] if isinstance(strategies, BaseException) else strategies
    lines = [
        f"{i['name']} [trend={i.get('bias') or 'ANY'}, side={i.get('optionSide') or 'ANY'}]: {i.get('description', '')}"
        for i in items
    ]
    analysis = analyze(cfg, market)
    found = setup_detector.detect(analysis, cfg)
    if found:
        logger.info(f"[SETUPS] {code} regime={analysis.get('regime')} "
                    + ", ".join(f"{s['name']}/{s['side']}/{s['strength']}" for s in found))
    return {"market": market, "strategies": lines, "strategyNames": [i["name"] for i in items],
            "analysis": analysis, "setups": found}


async def make_menu(state: UnderlyingState) -> dict[str, Any]:
    cfg = get_config(state["code"])
    analysis, setups = state["analysis"], state.get("setups") or []
    bias = direction_bias(state["research"], analysis)
    blocked = analysis["session"].get("blocked")
    if blocked and not state["params"].get("ignoreMarketHours"):
        return {"bias": bias, "menu": [], "error": blocked}
    brief = build_brief(cfg, state["research"], state["market"], bias, analysis, setups)  # type: ignore[arg-type]
    drop_reasons: dict[str, int] = {}
    menu = build_menu(  # type: ignore[arg-type]
        cfg, state["market"], bias, state["params"]["minProfitMargin"],
        max_margin=state["params"].get("maxProfitMargin", 10.0),
        max_stop=state["params"].get("maxStopLossPct", 5.0),
        reasons=drop_reasons,
        setups=setups,
    )
    for m in menu:
        m["underlyingType"] = cfg.type  # type: ignore[union-attr]
        m["volumeConfirmed"] = volume_confirms(analysis, m["side"])
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
        logger.info(f"[MENU_EMPTY] {state['code']} spot={state['market'].get('spot')} "
                    f"chains={[len(c['strikes']) for c in chains]} dropped={drop_reasons}")
    return out


def route_after_menu(state: UnderlyingState) -> str:
    if state.get("error"):
        return "end"
    return "validate" if state.get("reused") else "ai_select"


async def ai_select(state: UnderlyingState) -> dict[str, Any]:
    menu_for_ai = [{k: m.get(k) for k in _MENU_FIELDS_FOR_AI} for m in state["menu"]]
    user = (
        f"BRIEF:\n{state['brief']}\n\nSTRATEGY RULES:\n{state.get('strategies') or 'none'}\n\n"
        f"PAST HIT RATE (target hit before stop, this underlying): {state.get('hitRate')}\n\n"
        f"SIMILAR PAST CASES:\n{state.get('memory') or 'none'}\n\nMENU:\n{menu_for_ai}"
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
                        num_predict=900,
                        keep_alive="30m",
                    )
                ids = {m["id"] for m in state["menu"]}
                if answer.picks and all(p.id in ids for p in answer.picks):
                    break
                if not answer.picks and answer.noPickReason:
                    break
                answer = None
            except Exception as e:
                logger.warning(f"opportunities AI select failed ({state['code']}): {type(e).__name__}: {e}")
                answer = None
    if answer is None:
        return {"answer": {"picks": baseline_pick(state["menu"], state["bias"])}, "usedBaseline": True}
    dumped = answer.model_dump()
    _last_answer[state["code"]] = {"hash": state["briefHash"], "answer": dumped}
    return {"answer": dumped}


async def validate(state: UnderlyingState) -> dict[str, Any]:
    """Code checks every pick: on menu, fresh data, setup/volume/buildup adjustments, confidence, net edge."""
    p = state["params"]
    analysis, setups = state.get("analysis") or {}, state.get("setups") or []
    answer = state.get("answer") or _last_answer.get(state["code"], {}).get("answer", {"picks": []})
    by_id = {m["id"]: m for m in state["menu"]}
    fetched = datetime.fromisoformat(state["market"]["fetchedAt"])
    fresh = (datetime.utcnow() - fetched).total_seconds() <= MAX_DATA_AGE_SECONDS
    spot = state["market"]["spot"]
    live: dict[str, float] | None = None
    if not fresh and answer.get("picks"):
        # The AI step outlasted the freshness window: re-read the picked premiums once instead of dropping them.
        keys = [by_id[pk["id"]]["instrumentKey"] for pk in answer["picks"] if pk["id"] in by_id]
        live = await _live_prices(state["code"], keys)
        if live:
            fresh = True
    out: list[dict[str, Any]] = []
    dropped = {"stale": 0, "priceMoved": 0, "notOnMenu": 0, "lowConfidence": 0, "strategyRule": 0, "lowEdge": 0}
    setup_names = {s["name"].lower() for s in setups}
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
                continue
            m = {**m, "entry": round(ltp, 2),
                 "target": round(ltp * (1 + m["marginPct"] / 100), 2),
                 "stop": round(ltp * (1 - m["stopPct"] / 100), 2)}
        reasons = list(pk.get("reasons", []))
        risks = list(pk.get("risks", []))
        conf = int(pk["confidence"])
        if not state.get("usedBaseline"):  # baseline ranking already counts volume and setups
            adj = volume_adjustment(analysis, m["side"])
            if adj:
                conf += adj
                reasons.append("Futures volume spike confirms the move" if adj > 0 else "Thin futures volume, confidence reduced")
            s_adj, s = setup_adjustment(setups, m["side"])
            if s_adj:
                conf += s_adj
                reasons.append(f"Coded setup {s['name']} (strength {s['strength']}): {s['reason']}; "
                               f"chart target {s['target']} ({s['targetLevel']}), invalidation {s['stop']}")
        b_adj = buildup_adjustment(analysis, m["side"])
        if b_adj:
            conf += b_adj
            bu = analysis["buildup"]["state"].replace("_", " ").lower()
            (reasons if b_adj > 0 else risks).append(f"Futures {bu}")
        if analysis.get("regime") == "VOLATILE":
            conf -= 5
            risks.append("India VIX spiking: option premiums are expensive")
        if analysis.get("session", {}).get("window") == "MIDDAY_CHOP" and not m.get("setup"):
            conf -= 5
            risks.append("Midday chop window")
        conf = max(1, min(99, conf))
        if conf < p["confidenceWanted"] or m["marginPct"] < p["minProfitMargin"]:
            dropped["lowConfidence"] += 1
            continue
        edge = expected_edge_pct(conf, m["marginPct"], m["stopPct"], m.get("costPct", 0.0))
        if edge <= 0:
            dropped["lowEdge"] += 1
            continue
        reasons.append(f"Expected edge {edge:+.1f}% per trade after ~{m.get('costPct', 0)}% charges "
                       f"(target +{m['marginPct']}%, stop -{m['stopPct']}%)")
        if not m.get("withTrend", True):
            names = [n.lower() for n in state.get("strategyNames", [])]
            cited = (pk.get("strategy") or "").lower()
            ok_setup = bool(m.get("setup")) or (cited and any(n in cited or cited in n for n in setup_names))
            ok_strategy = bool(cited) and any(n in cited or cited in n for n in names)
            if not (ok_setup or ok_strategy or (not names and conf >= p["confidenceWanted"] + 10)):
                dropped["strategyRule"] += 1
                continue
            risks.insert(0, f"Against the {state['bias'].lower()} trend")
        out.append({**m, "underlyingCode": state["code"], "confidence": conf,
                    "strategy": pk.get("strategy") or m.get("setup"), "reasons": reasons,
                    "risks": risks, "bias": state["bias"], "edge": edge, "spot": spot,
                    "source": "BASELINE" if state.get("usedBaseline") else "AI"})
    total = len(answer.get("picks", []))
    regime = analysis.get("regime")
    setups_txt = ", ".join(f"{s['name']} {s['side']}" for s in setups) or "no coded setup"
    if out:
        note = f"{len(out)} opportunity(s) from {total} pick(s) · {regime} · {setups_txt}"
    elif total == 0:
        note = (answer.get("noPickReason") or "AI found no good contract on the menu") + f" · {regime} · {setups_txt}"
    else:
        why = ", ".join(f"{n} {k}" for k, n in dropped.items() if n)
        note = f"{total} pick(s) rejected ({why}); confidence needed {p['confidenceWanted']} · {regime} · {setups_txt}"
    return {"candidates": out, "note": note}


async def _live_prices(code: str, keys: list[str]) -> dict[str, float] | None:
    """Fresh LTP for the picked option instruments only, or None when it cannot be read."""
    try:
        async with async_session_factory() as s:
            return await market_data.ltp(keys, s)
    except Exception as e:
        logger.warning(f"opportunities reprice failed ({code}): {type(e).__name__}: {e}")
        return None
