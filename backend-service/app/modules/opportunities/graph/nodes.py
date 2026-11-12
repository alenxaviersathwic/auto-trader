import asyncio
import time
from collections import deque
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config.settings import settings
from app.core.db.session import async_session_factory
from app.core.logging.logger import logger
from app.modules.master.llm.ollama_client import OllamaClient
from app.modules.opportunities.graph.prompts import SELECT_SYSTEM_PROMPT
from app.modules.opportunities.graph.state import UnderlyingState
from app.modules.opportunities.provider.underlying_config import get_config, is_market_open
from app.modules.opportunities.provider.upstox_market_data import market_data
from app.modules.opportunities.schema.opportunity_schema import AiAnswer
from app.modules.opportunities.service import (
    chain_recorder,
    day_type,
    fii_open,
    gamma_regime,
    memory_service,
    positioning,
    timemachine,
)
from app.modules.opportunities.service import setups as setup_detector
from app.modules.opportunities.service.day_context import compute_calendar_tags, compute_expiry_tags
from app.modules.opportunities.service.market_analysis import analyze, oi_shift
from app.modules.opportunities.service.menu_builder import (
    baseline_pick,
    brief_hash,
    build_brief,
    build_menu,
    buildup_adjustment,
    direction_bias,
    expected_edge_pct,
    pcr_adjustment,
    setup_adjustment,
    strategy_stop_loss_for_pick,
    strike_mode,
    tag_adjustment,
    volume_adjustment,
    volume_confirms,
)
from app.modules.strategies.service.strategy_service import StrategyService

MAX_DATA_AGE_SECONDS = 120
REPRICE_TOLERANCE_PCT = 3.0  # after a slow AI step: keep a pick only if its premium moved less than this
_last_answer: dict[str, dict[str, Any]] = {}  # code -> {"hash": str, "answer": dict}
_last_noise: dict[str, dict[str, Any]] = {}
_gex_hist: dict[str, deque[float]] = {}  # code -> recent net GEX readings (tercile reference); single process
_positioning: dict[str, Any] = {"date": None, "state": {}}
_last_gamma: dict[str, dict[str, Any]] = {}  # code -> latest gamma read (iron fly paper engine reads it)
_IST_TZ = ZoneInfo("Asia/Kolkata")
POSITIONING_ADJ = 5  # confidence points; stands in for the review's x1.5 / x0.5 size tilt


def _positioning_state() -> dict[str, Any]:
    today = datetime.now(_IST_TZ).date()
    if _positioning["date"] != today:
        try:
            state = positioning.snapshot(today)
        except Exception:  # noqa: BLE001
            state = {}
        _positioning.update(date=today, state=state)
    return _positioning["state"]


def _gamma_state(code: str, market: dict[str, Any], pos: dict[str, Any]) -> dict[str, Any]:
    """Net GEX of the nearest chain, its tercile regime vs this process's recent history, and the router verdict."""
    chains = [c for c in market.get("chains") or [] if c.get("strikes") and c.get("expiry")]
    if not chains or not market.get("spot"):
        return {}
    call_s, put_s = gamma_regime.participant_signs(pos.get("client"))
    try:
        gex = gamma_regime.net_gex(chains[0], market["spot"], datetime.now(_IST_TZ), call_s, put_s)
    except Exception:  # noqa: BLE001 -- a malformed chain must not stop the iteration
        return {}
    hist = _gex_hist.setdefault(code, deque(maxlen=3000))
    reg = gamma_regime.regime(gex, list(hist))
    hist.append(gex)
    out = {"gex": round(gex / 1e7, 2), "unit": "Rs crore per 1%", "regime": reg, "route": gamma_regime.route(reg),
           "signs": {"call": call_s, "put": put_s}, "enabled": settings.GAMMA_ROUTER_ENABLED}
    _last_gamma[code] = out
    return out  # code -> latest noise-area read (iron fly paper engine reads it)
_day_bias: dict[str, dict[str, Any]] = {}  # code -> {"date": date, "bias": day_type.apply_bias() dict}; reset daily
_strategy_service = StrategyService()
_llm = OllamaClient()
# One local model serves every card; the frontend iterates cards one by one. Cap overlap at 2.
_ai_gate = asyncio.Semaphore(2)
AI_TIMEOUT_SECONDS = 180.0
MIN_DELTA = 0.5  # ATM / one-strike-ITM contracts only, and never a lottery-ticket delta
# code -> recent option-chain OI snapshots (time.monotonic(), {pcr, ceOi, peOi}); single process, so memory is enough
_oi_history: dict[str, deque[tuple[float, dict[str, float]]]] = {}
OI_SHIFT_MIN_AGE = 300.0  # compare against a snapshot at least 5 minutes old...
OI_SHIFT_MAX_AGE = 1800.0  # ...and at most 30 minutes old
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
        f"{i['name']} [trend={i.get('bias') or 'ANY'}, side={i.get('optionSide') or 'ANY'}, "
        f"winRate={i.get('winRatePct') if i.get('winRatePct') is not None else 'N/A'}%, "
        f"stopLossPct={i.get('stopLossPct')}%]: {i.get('description', '')}"
        for i in items
    ]
    strategy_stop_loss = {
        i["name"]: float(i["stopLossPct"])
        for i in items
        if i.get("stopLossPct") is not None
    }
    await chain_recorder.record(code, market)
    market["sessions5"] = await _noise_sessions(cfg, market)
    analysis = analyze(cfg, market)
    analysis["dayBias"] = _session_day_bias(code, analysis.get("dayType"))
    if analysis.get("noise"):
        _last_noise[code] = analysis["noise"]
    pos = _positioning_state()
    analysis["positioning"] = {k: pos.get(k) for k in ("asOf", "fiiLongRatio", "ratio5", "bias")} if pos else {}
    analysis["gamma"] = _gamma_state(code, market, pos)
    _attach_oi_shift(code, analysis)
    await _attach_institutional_inputs(cfg, analysis)
    raw = setup_detector.detect(analysis, cfg)
    found, rejected = setup_detector.confirm_timeframes(analysis, raw)
    fo = fii_open.signal(code, analysis.get("spot") or market.get("spot"))
    if fo and not any(x["name"] == fo["name"] for x in found):
        found = [fo, *found]  # opening trade: not a chart setup, so it skips the timeframe / momentum gates
        logger.info(f"[FII_OPEN] {code} {fo['reason']}")
    diag = {"regime": analysis.get("regime"), "dayType": analysis.get("dayType"), "dayBias": analysis.get("dayBias"),
            "gamma": analysis.get("gamma"), "positioning": analysis.get("positioning"),
            "noise": analysis.get("noise"),
            "dte": analysis.get("dte"), "window": analysis["session"].get("window"),
            "trend15": analysis.get("trend15"), "trend15Source": analysis.get("trend15Source"),
            "setupsFired": [{"name": s["name"], "side": s["side"], "strength": s["strength"]} for s in raw],
            "setupsConfirmed": [{"name": s["name"], "side": s["side"], "strength": s["strength"]} for s in found],
            "setupsRejected": rejected}
    if found or rejected:
        logger.info(f"[SETUPS] {code} regime={analysis.get('regime')} confirmed="
                    + ", ".join(f"{s['name']}/{s['side']}/{s['strength']}" for s in found)
                    + " rejected=" + ", ".join(f"{r['name']}/{r['side']}" for r in rejected))
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    day_tags = compute_calendar_tags(now_ist, cfg.exchange) + compute_expiry_tags(  # type: ignore[union-attr]
        now_ist.date(), market.get("chains", [])
    )
    return {"market": market, "strategies": lines, "strategyNames": [i["name"] for i in items],
            "strategyTags": {i["name"]: i.get("tags") or [] for i in items},
            "strategyStopLoss": strategy_stop_loss, "dayTags": day_tags,
            "analysis": analysis, "setups": found, "diag": diag}


def _session_day_bias(code: str, day_type_now: dict[str, Any] | None) -> dict[str, Any] | None:
    """Sticky day-type call for TODAY's session (day_type.apply_bias(), 10 Nov 2026 post-mortem): once this
    underlying has confirmed EXPANSION on a side today, keeps remembering it through later snapshots that read
    back as a RANGE/PIN pullback -- but only once a new direction has held for day_type.MIN_PERSIST_MIN minutes,
    so a brief opening whipsaw can't lock in the wrong side for the rest of the session. Reset whenever the date
    rolls over (single process; fine for one backend)."""
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    today = now_ist.date()
    entry = _day_bias.get(code)
    state = entry["state"] if entry and entry["date"] == today else {}
    state = day_type.apply_bias(day_type_now or {}, state, now_ist.hour * 60 + now_ist.minute)
    _day_bias[code] = {"date": today, "state": state}
    return state.get("bias")


async def _noise_sessions(cfg: Any, market: dict[str, Any]) -> list:
    """Past sessions of 5-minute bars for the noise area (the Time Machine's once-a-day cache); [] when unavailable."""
    key = market.get("futuresKey") if cfg.type == "COMMODITY" else cfg.instrumentKey

    async def fetch(k: str) -> list[dict[str, Any]]:
        async with async_session_factory() as s:
            return await market_data.candles_5m_history(k, s, timemachine.HISTORY_DAYS)

    try:
        got = await timemachine.pool_for(key, cfg.open, fetch)
    except Exception as e:  # the noise area falls back to the ATR proxy
        logger.warning(f"[DAY_TYPE] {cfg.code} history unavailable: {type(e).__name__}: {e}")
        return []
    return got[0] if got else []


HEAVY_KEYS = {"HDFCBANK": "NSE_EQ|INE040A01034", "ICICIBANK": "NSE_EQ|INE090A01021", "RELIANCE": "NSE_EQ|INE002A01018",
              "INFY": "NSE_EQ|INE009A01021", "BHARTIARTL": "NSE_EQ|INE397D01024", "SBIN": "NSE_EQ|INE062A01020",
              "AXISBANK": "NSE_EQ|INE238A01034", "KOTAKBANK": "NSE_EQ|INE237A01028"}
_inst_cache: dict[str, tuple[float, Any]] = {}


async def _attach_institutional_inputs(cfg: Any, analysis: dict[str, Any]) -> None:
    """Live inputs for the institutional filters that need extra data -- fetched only when that filter is on:
    OI_BUILDUP (yesterday's near-month futures price / OI change, cached per day) and HEAVYWEIGHTS (5 stocks'
    1-minute bars vs their VWAP, cached 60 s). India VIX is already in the analysis (market fetch)."""
    from app.modules.opportunities.service import institutional_filters as inst

    on = inst.enabled(settings.INSTITUTIONAL_FILTERS)
    code = cfg.code
    try:
        if "OI_BUILDUP" in on:
            key = f"oi:{code}:{datetime.now(_IST_TZ).date()}"
            if key not in _inst_cache:
                async with async_session_factory() as s:
                    fd = await market_data.futures_daily(cfg, s)
                today = datetime.now(_IST_TZ).date().isoformat()
                prev = [b for b in fd if str(b.get("t", ""))[:10] < today][-2:]
                st = inst.buildup_state(prev[1]["c"] - prev[0]["c"], (prev[1].get("oi") or 0) - (prev[0].get("oi") or 0)) \
                    if len(prev) == 2 else None
                _inst_cache[key] = (time.monotonic(), st)
            analysis["oiBuildupDaily"] = _inst_cache[key][1]
        if "HEAVYWEIGHTS" in on and code in inst.HEAVYWEIGHTS:
            key = f"hw:{code}"
            hit = _inst_cache.get(key)
            if not hit or time.monotonic() - hit[0] > 60:
                names = inst.HEAVYWEIGHTS[code]
                async with async_session_factory() as s:
                    raw = await market_data.intraday_1m([HEAVY_KEYS[n] for n in names], s)
                hit = (time.monotonic(), inst.heavyweight_state({n: raw.get(HEAVY_KEYS[n]) or [] for n in names}))
                _inst_cache[key] = hit
            analysis["heavyweights"] = hit[1]
    except Exception as e:  # noqa: BLE001 -- missing inputs never veto (filters treat them as unknown)
        logger.warning(f"[INST_INPUTS] {code}: {type(e).__name__}: {e}")


def _attach_oi_shift(code: str, analysis: dict[str, Any]) -> None:
    """Record this iteration's chain OI snapshot and compare it with one 5-30 minutes old (PCR_SHIFT input)."""
    oi = analysis.get("oi") or {}
    if not oi.get("ceOi") or not oi.get("peOi") or oi.get("pcr") is None:
        return
    now = time.monotonic()
    cur = {"pcr": float(oi["pcr"]), "ceOi": float(oi["ceOi"]), "peOi": float(oi["peOi"])}
    hist = _oi_history.setdefault(code, deque(maxlen=200))
    while hist and now - hist[0][0] > OI_SHIFT_MAX_AGE:
        hist.popleft()
    old = next((snap for ts, snap in hist if now - ts >= OI_SHIFT_MIN_AGE), None)
    shift = oi_shift(old, cur)
    if shift:
        analysis["oiShift"] = shift
    hist.append((now, cur))


async def make_menu(state: UnderlyingState) -> dict[str, Any]:
    cfg = get_config(state["code"])
    analysis, setups = state["analysis"], state.get("setups") or []
    bias = direction_bias(state["research"], analysis)
    diag = dict(state.get("diag") or {})
    blocked = analysis["session"].get("blocked")
    if blocked and not state["params"].get("ignoreMarketHours"):
        return {"bias": bias, "menu": [], "error": blocked, "diag": {**diag, "result": "BLOCKED_WINDOW", "reason": blocked}}
    if not setups:
        fired = diag.get("setupsFired") or []
        rejected = diag.get("setupsRejected") or []
        if fired:
            why = "; ".join(f"{r['name']} {r['side']}: {r['reason']}" for r in rejected[:4])
            return {"bias": bias, "menu": [], "error": f"{len(fired)} setup(s) fired but failed timeframe agreement ({why})",
                    "diag": {**diag, "result": "SETUP_REJECTED", "reason": why}}
        return {"bias": bias, "menu": [], "error": f"no setup fired · {analysis.get('regime')} · 15m {analysis.get('trend15')}",
                "diag": {**diag, "result": "NO_SETUP", "reason": "no coded setup fired on the last completed 5-minute bar"}}
    brief = build_brief(cfg, state["research"], state["market"], bias, analysis, setups,  # type: ignore[arg-type]
                        state.get("dayTags"), state.get("strategyTags"))
    drop_reasons: dict[str, int] = {}
    strat_stops = [float(v) for v in (state.get("strategyStopLoss") or {}).values() if v and v > 0]
    effective_max_stop = max(strat_stops) if strat_stops else float(state["params"].get("maxStopLossPct", 3.5))
    strike_modes = {side: strike_mode(analysis, next((s for s in setups if s["side"] == side and not s.get("conflict")), None))
                    for side in ("CE", "PE")} if cfg.type == "INDEX" else None  # type: ignore[union-attr]
    diag["strikeModes"] = strike_modes
    menu = build_menu(  # type: ignore[arg-type]
        cfg, state["market"], bias, state["params"]["minProfitMargin"],
        max_margin=state["params"].get("maxProfitMargin", 10.0),
        max_stop=effective_max_stop,
        reasons=drop_reasons,
        setups=setups,
        require_setup=True,
        atm_itm_only=True,
        min_delta=MIN_DELTA,
        atr5=analysis.get("atr5") or None,
        strike_modes=strike_modes,
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
    diag["menuSize"], diag["menuDropped"] = len(menu), dict(drop_reasons)
    out: dict[str, Any] = {"bias": bias, "brief": brief, "briefHash": h, "menu": menu, "reused": reused,
                           "memory": memory, "hitRate": hits, "diag": diag}
    if not menu:
        chains = state["market"].get("chains", [])
        if not chains:
            out["error"] = "no option chain returned for this underlying"
        elif not drop_reasons:
            out["error"] = "option chain had no strikes near spot"
        else:
            why = ", ".join(f"{n} {k}" for k, n in sorted(drop_reasons.items(), key=lambda x: -x[1]))
            out["error"] = f"no executable contract -- dropped: {why}"
        out["diag"] = {**diag, "result": "NO_CONTRACT", "reason": out["error"]}
        logger.info(f"[MENU_EMPTY] {state['code']} spot={state['market'].get('spot')} "
                    f"chains={[len(c['strikes']) for c in chains]} dropped={drop_reasons}")
    return out


def route_after_menu(state: UnderlyingState) -> str:
    if state.get("error"):
        return "end"
    return "validate" if state.get("reused") else "ai_select"


_shadow_tasks: set[asyncio.Task] = set()


async def ai_select(state: UnderlyingState) -> dict[str, Any]:
    """11 Nov 2026 research review (gap 7): there is no evidence the LLM ranker adds edge (FINSABER 2025, StockBench,
    LiveOption; the 75-84 confidence bucket won 0% on 4 Nov). With OPPORTUNITY_RANKER=CODE (default) the code
    baseline decides immediately -- no 60-180 s model wait on a 20-second trade -- and the LLM runs in SHADOW in the
    background: its pick is logged next to the baseline's ([AI_SHADOW]) so the two can be A/B'd on outcomes.
    The LLM goes back in charge only if it beats the baseline by >= 0.05R on >= 200 matched shadow trades."""
    if (settings.OPPORTUNITY_RANKER or "CODE").upper() != "LLM":
        base = baseline_pick(state["menu"], state["bias"])
        for b in base:
            b["risks"] = [r for r in b.get("risks", []) if "AI unavailable" not in r] + ["code ranking (LLM in shadow)"]
        if settings.OPPORTUNITY_LLM_SHADOW and state["menu"]:
            task = asyncio.create_task(_shadow(state, [b["id"] for b in base[:3]]))
            _shadow_tasks.add(task)
            task.add_done_callback(_shadow_tasks.discard)
        return {"answer": {"picks": base}, "usedBaseline": True}
    return await _llm_select(state)


async def _shadow(state: UnderlyingState, baseline_ids: list[str]) -> None:
    try:
        res = await _llm_select(state)
        picks = [(p.get("id"), p.get("confidence")) for p in (res.get("answer") or {}).get("picks", [])][:3]
        logger.info(f"[AI_SHADOW] {state['code']} hash={state.get('briefHash')} baseline={baseline_ids} "
                    f"llm={picks} llmFellBack={bool(res.get('usedBaseline'))}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[AI_SHADOW] {state['code']}: {type(e).__name__}: {e}")


async def _llm_select(state: UnderlyingState) -> dict[str, Any]:
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
                        # qwen3:8b on the Mac mini decodes at ~15 tok/s; 900 was hitting the cap mid-JSON
                        # on anything but a trivial menu (log: "answer=900tok/58.5s" then a JSON parse
                        # failure), which silently fell back to the conservative baseline picker and
                        # explained most of the "N pick(s) rejected (lowConfidence)" runs. 2048 tokens is
                        # still comfortably inside AI_TIMEOUT_SECONDS (180s) at this decode speed.
                        num_predict=2048,
                        keep_alive="30m",
                    )
                ids = {m["id"] for m in state["menu"]}
                if answer.picks and all(p.id in ids for p in answer.picks):
                    break
                answer = None
            except Exception as e:
                logger.warning(f"opportunities AI select failed ({state['code']}): {type(e).__name__}: {e}")
                answer = None
    if answer is None:
        return {"answer": {"picks": baseline_pick(state["menu"], state["bias"])}, "usedBaseline": True}
    dumped = answer.model_dump()
    if (settings.OPPORTUNITY_RANKER or "CODE").upper() == "LLM":
        # only a LIVE LLM answer may be reused for an unchanged brief; a shadow answer must never reach validate()
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
    dropped = {"stale": 0, "priceMoved": 0, "notOnMenu": 0, "lowConfidence": 0, "strategyRule": 0, "lowEdge": 0,
               "timeMachine": 0}
    tm_ctx = await _time_machine_context(state) if answer.get("picks") else None
    tm_seen: list[dict[str, Any]] = []
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
        strat_sl_pct, strat_sl_src = strategy_stop_loss_for_pick(
            state.get("strategyStopLoss"), pk.get("strategy")
        )
        # point-based exits already sit on the chart structure: a strategy's fixed % stop would pull the stop back
        # inside one bar's noise, so it only applies to percentage-mode picks
        if strat_sl_pct is not None and strat_sl_pct > 0 and m.get("exitMode") != "POINTS":
            applied_sl = round(min(strat_sl_pct, float(m.get("marginPct", strat_sl_pct)) / 1.2), 1)
            if applied_sl >= 1.5:
                entry_px = float(m["entry"])
                new_stop = round(entry_px * (1 - applied_sl / 100.0), 2)
                new_rr = round(float(m["marginPct"]) / applied_sl, 2)
                m = {**m, "stop": new_stop, "stopPct": applied_sl, "rewardRisk": new_rr}
                reasons.append(f"Stop loss -{applied_sl}% driven by {strat_sl_src} win-rate stop loss ({strat_sl_pct}%)")
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
        p_adj = pcr_adjustment(analysis, m["side"])
        if p_adj:
            conf += p_adj
            sh = analysis["oiShift"]
            reasons.append(f"PCR drift confirms (PCR {sh['pcrChg']:+.2f} to {sh['pcr']}) -- confluence only")
        t_adj, matched_tags = tag_adjustment(state.get("dayTags") or [], state.get("strategyTags") or {},
                                             pk.get("strategy"))
        if t_adj:
            conf += t_adj
            reasons.append(f"Strategy tagged for today's conditions ({', '.join(matched_tags)})")
        if analysis.get("regime") == "VOLATILE":
            conf -= 5
            risks.append("India VIX spiking: option premiums are expensive")
        if analysis.get("session", {}).get("window") == "MIDDAY_CHOP" and not m.get("setup"):
            conf -= 5
            risks.append("Midday chop window")
        pos_bias = (analysis.get("positioning") or {}).get("bias") or 0
        if settings.POSITIONING_OVERLAY_ENABLED and pos_bias:
            # institutional review Strategy 4: FII positioning tilts, never decides (stand-alone versions lost)
            with_fii = (m["side"] == "CE") == (pos_bias > 0)
            conf += POSITIONING_ADJ if with_fii else -POSITIONING_ADJ
            reasons.append(f"FII index-futures positioning {'agrees' if with_fii else 'disagrees'} "
                           f"(long ratio {analysis['positioning'].get('ratio5')})")
        conf = max(1, min(99, conf))
        # out-of-the-money premium exits cannot be mapped onto the underlying through delta (gamma): no replay
        tm = _run_time_machine(tm_ctx, m, spot) if m.get("exitMode") != "PREMIUM" else None
        tm_ok = bool(tm and timemachine.judged(tm))
        if tm:
            tm_seen.append({"id": m["id"], "pTarget": tm["pTarget"], "pStop": tm["pStop"], "lean": tm["lean"]})
            h = tm["history"]
            reasons.append(
                f"Time Machine ({tm['replays']:,} replays of the next {tm['barsAhead'] * 5} min from the last "
                f"{h['sessions']} sessions, seed {tm['seed']}): target first {tm['pTarget'] * 100:.1f}%, "
                f"stop first {tm['pStop'] * 100:.1f}%, neither {tm['pNeither'] * 100:.1f}% · real history "
                f"{h['target']} target / {h['stop']} stop / {h['neither']} neither · {tm['verdict']}")
        if tm_ok and tm["lean"] <= timemachine.DROP_LEAN:
            dropped["timeMachine"] += 1
            continue
        if tm_ok:
            # calibrate the AI's number with what the underlying actually did at this time of day
            conf = max(1, min(99, round((conf + 100 * tm["targetShare"]) / 2)))
        if conf < p["confidenceWanted"] or m["marginPct"] < p["minProfitMargin"]:
            dropped["lowConfidence"] += 1
            continue
        if tm_ok:
            edge = timemachine.edge_pct(tm, m["marginPct"], m["stopPct"], m.get("costPct", 0.0))
        else:
            edge = expected_edge_pct(conf, m["marginPct"], m["stopPct"], m.get("costPct", 0.0))
        if edge <= 0:
            dropped["lowEdge"] += 1
            continue
        reasons.append(f"Expected edge {edge:+.1f}% per trade after ~{m.get('costPct', 0)}% charges "
                       f"(target +{m['marginPct']}%, stop -{m['stopPct']}%"
                       + (", from the Time Machine odds)" if tm_ok else ", from the confidence)"))
        reasons.append(_sizing_note(m, float(p.get("riskPerTradeRs") or DEFAULT_RISK_PER_TRADE_RS), analysis))
        if m.get("strikeMode") == "LOTTERY":
            risks.insert(0, "Far out-of-the-money on expiry afternoon: the whole premium can go to zero")
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
                    "risks": risks, "bias": state["bias"], "edge": edge, "spot": spot, "timeMachine": tm,
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
    diag = {**(state.get("diag") or {}), "picks": total, "kept": len(out),
            "dropped": {k: n for k, n in dropped.items() if n},
            "source": "BASELINE" if state.get("usedBaseline") else "AI", "confidenceWanted": p["confidenceWanted"],
            "timeMachine": {"ready": tm_ctx is not None, "picks": tm_seen}}
    if out:
        diag["result"] = "SAVED"
    else:
        diag["result"] = "DROPPED"
        diag["reason"] = note
    return {"candidates": out, "note": note, "diag": diag}


DEFAULT_RISK_PER_TRADE_RS = 2000.0


def _sizing_note(m: dict[str, Any], risk_rs: float, analysis: dict[str, Any]) -> str:
    """Strike mode, exits and fixed-rupee sizing in one line a trader can act on."""
    per_lot = float(m.get("riskPerLot") or 0)
    lots = int(risk_rs // per_lot) if per_lot > 0 else 0
    dt = (analysis.get("dayType") or {}).get("type") or "day type n/a"
    size = (f"{lots} lot(s) for a Rs {risk_rs:,.0f} risk" if lots >= 1
            else f"1 lot risks Rs {per_lot:,.0f}, above the Rs {risk_rs:,.0f} risk per trade")
    tstop = f", exit if no new high in {m['timeStopMin']} min" if m.get("timeStopMin") else ""
    return (f"{dt} day · strike mode {m.get('strikeMode') or 'ATM'} (delta {m.get('delta')}) · {m.get('exitMode')} exits"
            f"{tstop} · risk Rs {per_lot:,.0f} per lot -> {size}")


async def _time_machine_context(state: UnderlyingState) -> tuple[list, dict, int, int] | None:
    """(sessions, pool, k, last) for this underlying, or None when the history or the clock does not allow it.
    Index: the spot index's own 5-minute bars. Commodity: the near-month future the analysis already reads."""
    cfg = get_config(state["code"])
    bars5 = (state.get("analysis") or {}).get("bars5") or []
    if not cfg or not bars5:
        return None
    key = state["market"].get("futuresKey") if cfg.type == "COMMODITY" else cfg.instrumentKey

    async def fetch(k: str) -> list[dict[str, Any]]:
        async with async_session_factory() as s:
            return await market_data.candles_5m_history(k, s, timemachine.HISTORY_DAYS)

    got = await timemachine.pool_for(key, cfg.open, fetch)
    if not got:
        return None
    k, last = timemachine.horizon(cfg.open, cfg.close_today(), bars5[-1]["t"],
                                  int(state["params"].get("validMinutes", 15)))
    if last <= k:
        return None
    return got[0], got[1], k, last


def _run_time_machine(ctx: tuple[list, dict, int, int] | None, m: dict[str, Any], spot: float) -> dict[str, Any] | None:
    """Replay the pick's OWN premium target/stop, mapped onto the underlying through its delta (the levels the
    outcome checker grades), from the current spot. Gamma and theta are ignored: a first-order map."""
    if not ctx or not spot or not m.get("entry"):
        return None
    delta = abs(m.get("delta") or 0) or 0.5
    up = m["side"] == "CE"
    tgt_move = m["entry"] * m["marginPct"] / 100 / delta
    stop_move = m["entry"] * m["stopPct"] / 100 / delta
    target = spot + tgt_move if up else spot - tgt_move
    stop = spot - stop_move if up else spot + stop_move
    try:
        return timemachine.evaluate(ctx[0], ctx[1], spot, stop, target, up, ctx[2], ctx[3])
    except Exception as e:  # never let the odds step kill an iteration
        logger.warning(f"[TIME_MACHINE] {m.get('id')}: {type(e).__name__}: {e}")
        return None


async def _live_prices(code: str, keys: list[str]) -> dict[str, float] | None:
    """Fresh LTP for the picked option instruments only, or None when it cannot be read."""
    try:
        async with async_session_factory() as s:
            return await market_data.ltp(keys, s)
    except Exception as e:
        logger.warning(f"opportunities reprice failed ({code}): {type(e).__name__}: {e}")
        return None
