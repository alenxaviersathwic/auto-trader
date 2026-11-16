"""
LangGraph LLM Decision & Trailing SL Engine (`trader_llm_graph.py`).

Two compiled LangGraph StateGraphs:
  1. `opportunity_selector_graph`:
     START -> assess_risk_budget -> llm_rank_and_pick -> END
     Communicates with the local LLM (Ollama) to decide which candidate opportunity
     is strongest for the session's Risk Profile & active Traders, then returns the pick to lock.

  2. `position_trail_graph`:
     START -> analyze_microstructure -> llm_trail_decision -> enforce_invariants -> END
     Communicates with the local LLM (Ollama) to evaluate a running position's 1m candles,
     volume, RSI, and Risk Profile, deciding whether to HOLD, TRAIL_SL, STEP_TARGET, or EXIT_NOW.

Both graphs gracefully fall back to deterministic institutional rules (`trader_brain`) when the
local LLM is offline or times out, so live trading never stalls.
"""
from datetime import datetime
from typing import Any, Literal, TypedDict
from zoneinfo import ZoneInfo

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.core.logging.logger import logger
from app.modules.master.llm.ollama_client import OllamaClient
from app.modules.trades.service import trader_brain

_llm = OllamaClient()

MANAGER_PLAYBOOKS: dict[str, dict[str, str]] = {
    "FIB_GOLDEN_TRADER": {
        "title": "Session Manager 1 · My Experience (Discretionary Trader Psychology)",
        "selectionRule": (
            "Prefer patient 0.50–0.618 Golden Pocket pullbacks backed by Put/Call OI walls; "
            "reject FOMO chasing above entry band and require strict SL behind 0.786 retracement."
        ),
        "trailRule": (
            "Honour 0.786 initial SL; at 80% of 1.0 Swing High lock SL at 0.618 (~50% move); "
            "at 1.0 Target with strong volume lock SL at 1.0 and step Target to 1.272 / 1.618 Fib extension."
        ),
    },
    "FLOW_MOMENTUM_TRADER": {
        "title": "Session Manager 2 · Indian Quant Desk (NIFTY/BANKNIFTY/SENSEX LLM Flow)",
        "selectionRule": (
            "Indian index scalping desk: prefer current weekly ATM (Delta ~0.45–0.50) or 1-ITM (Delta ~0.60); "
            "require Spot strictly above/below Session VWAP & 9-EMA, Call/Put OI unwinding + PCR alignment, "
            "and respect India VIX (12–18 ideal; <12 choppy lower target; >20 reduce size). "
            "Avoid sideways VWAP chop during Mid-Day Theta Slump (11:30–13:30 IST); prioritize 09:15–11:30 ORB & 13:30–15:15 Gamma Window."
        ),
        "trailRule": (
            "State 0: Hard 15%–25% premium SL, never average down. "
            "State 1 (+1.0R): Lock Breakeven + brokerage/STT/slippage. "
            "States 2–3 (+1.5R to +2.0R): Trail tighter of 5-EMA/9-EMA or 50% peak lock; exit immediately if spot crosses opposite side of VWAP or after 15:15 IST."
        ),
    },
}


INDEX_PROFILES: dict[str, str] = {
    "NIFTY": (
        "NIFTY (NSE, Weekly Expiry: Tuesday): Cleanest trend & VWAP/PDH/PDL/CPR respect, tightest spreads. "
        "Watch round-number OI walls & Call OI unwinding for short-covering breakouts. "
        "Entry order: Limit order with +1 to +2 pts buffer (never raw market order on spikes). "
        "Strikes: ATM (Delta ~0.50) or 1-strike ITM (Delta ~0.60)."
    ),
    "BANKNIFTY": (
        "BANKNIFTY (NSE, Monthly Expiry): High-beta 100-200pt whipsaws & slingshot Gamma traps. "
        "Require strict Delta-OI confirmation + narrow CPR/VWAP alignment; avoid chasing fake breakouts."
    ),
    "SENSEX": (
        "SENSEX (BSE, Weekly Expiry: Thursday): Thinner book and wider spreads in morning; explosive Thursday PM Gamma bursts (13:30-15:10 IST). "
        "Strict spread check ((Ask-Bid)/Mid <= 0.5%), strictly high-volume ITM strikes (avoid deep OTM traps). "
        "Entry order: Limit order with +3 to +5 pts buffer to prevent catastrophic slippage on reversal snaps. "
        "Enforce fast +1.0R BE lock to survive violent slingshots."
    ),
    "FINNIFTY": (
        "FINNIFTY (NSE, Monthly Expiry): Financial-heavyweight correlated with BANKNIFTY; respect VWAP & PDH/PDL."
    ),
    "MIDCPNIFTY": (
        "MIDCPNIFTY (NSE, Monthly Expiry): Midcap index with thinner option book; prefer ATM/1-ITM & tight limit fills."
    ),
}


def _index_profile_note(symbol_or_contract: str | None) -> str:
    text = (symbol_or_contract or "").upper()
    for key, note in INDEX_PROFILES.items():
        if key in text:
            return note
    return (
        "Index/F&O Contract: Check 15m ORB (09:15-09:30), PDH/PDL, Narrow vs Wide CPR, "
        "Delta-OI (Call unwinding + Put addition for CE; Put unwinding + Call addition for PE), "
        "and apply a 15-20 min Time Stop if momentum stalls."
    )


def _ist_session_window() -> tuple[str, str]:
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    hhmm = now_ist.strftime("%H:%M")
    mins = now_ist.hour * 60 + now_ist.minute
    if mins < 11 * 60 + 30:
        return hhmm, "MORNING_ORB (09:15–11:30 IST)"
    if mins < 13 * 60 + 30:
        return hhmm, "MIDDAY_THETA_SLUMP (11:30–13:30 IST — avoid VWAP chop)"
    if mins < 15 * 60 + 15:
        return hhmm, "GAMMA_WINDOW (13:30–15:15 IST — short-covering/momentum)"
    return hhmm, "EOD_SQUAREOFF (>=15:15 IST — exit intraday options)"


def _get_playbook(trader_code: str | None) -> dict[str, str]:
    return MANAGER_PLAYBOOKS.get(
        trader_code or "FLOW_MOMENTUM_TRADER",
        MANAGER_PLAYBOOKS["FLOW_MOMENTUM_TRADER"],
    )


# ───────────────────────── Structured LLM Schemas ─────────────────────────
class LlmPickSelection(BaseModel):
    selectedOpportunityId: int = Field(..., description="ID of the best opportunity to lock")
    confidence: int = Field(..., ge=1, le=100)
    recommendedLots: int = Field(default=1, ge=1)
    reasoning: str = Field(..., min_length=5, max_length=400)


class LlmTrailDecision(BaseModel):
    action: Literal["HOLD", "TRAIL_SL", "STEP_TARGET", "EXIT_NOW"]
    newStop: float = Field(..., gt=0)
    newTarget: float = Field(..., gt=0)
    reasoning: str = Field(..., min_length=5, max_length=400)


# ───────────────────────── Graph 1: Opportunity Selector ─────────────────────────
class SelectorState(TypedDict, total=False):
    sessionId: int
    traderCode: str
    riskLevel: str
    availableCapital: float
    remainingLossBudget: float
    activeTradesCount: int
    candidates: list[dict[str, Any]]
    selection: dict[str, Any]
    usedFallback: bool


async def _assess_risk_budget(state: SelectorState) -> dict[str, Any]:
    candidates = state.get("candidates") or []
    # Sort best-first by expectedNet, confidence, rewardRisk
    ordered = sorted(
        candidates,
        key=lambda c: (
            float(c.get("expectedNet") or 0),
            int(c.get("confidence") or 0),
            float(c.get("rewardRisk") or 0),
        ),
        reverse=True,
    )
    return {"candidates": ordered[:5]}


async def _llm_rank_and_pick(state: SelectorState) -> dict[str, Any]:
    candidates = state.get("candidates") or []
    if not candidates:
        return {"selection": {}, "usedFallback": True}

    top = candidates[0]
    fallback = {
        "selectedOpportunityId": int(top["id"]),
        "confidence": int(top.get("confidence") or 75),
        "recommendedLots": int(top.get("lots") or 1),
        "reasoning": (
            f"Selected #{top['id']} ({top.get('underlyingCode')} {top.get('strike')} {top.get('optionType')}) "
            f"— highest expected net edge with {top.get('confidence')}% confidence & {top.get('rewardRisk')} R:R."
        ),
    }

    try:
        if await _llm._resolve_healthy_url():
            summary_rows = [
                {
                    "id": c.get("id"),
                    "contract": f"{c.get('underlyingCode')} {c.get('strike')} {c.get('optionType')}",
                    "strategy": c.get("strategy"),
                    "trader": c.get("traderCode"),
                    "confidence": c.get("confidence"),
                    "rewardRisk": c.get("rewardRisk"),
                    "entry": c.get("entry"),
                    "stop": c.get("stop"),
                    "target": c.get("target"),
                    "lots": c.get("lots", 1),
                    "expectedNet": c.get("expectedNet", 0),
                }
                for c in candidates
            ]
            playbook = _get_playbook(state.get("traderCode") or str(top.get("traderCode") or ""))
            ist_time, ist_window = _ist_session_window()
            idx_note = _index_profile_note(str(top.get("underlyingCode") or ""))
            prompt = (
                f"You are an institutional Indian options desk Risk & Opportunity Selector.\n"
                f"IST Clock: {ist_time} | Session Window: {ist_window}\n"
                f"Index Profile: {idx_note}\n"
                f"Index Confluence Gate: Prefer 15m ORB + PDH/PDL/Narrow CPR + VWAP alignment + Delta-OI confirmation; "
                f"reject wide-CPR chop, VWAP conflicts, and unconfirmed expiry Gamma traps.\n"
                f"Manager Mode: {playbook['title']}\n"
                f"Manager Psychology Rule: {playbook['selectionRule']}\n"
                f"Session Risk Level: {state.get('riskLevel', 'L2_BALANCED')}, "
                f"Free Capital: ₹{state.get('availableCapital', 0):.0f}, "
                f"Open Parallel Trades: {state.get('activeTradesCount', 0)}/3.\n"
                f"Candidates: {summary_rows}\n"
                f"Pick the single best opportunity ID to lock right now and explain why concisely."
            )
            res: LlmPickSelection = await _llm.generate_structured(
                prompt=prompt,
                schema=LlmPickSelection,
                timeout=12.0,
            )
            valid_ids = {int(c["id"]) for c in candidates}
            if res.selectedOpportunityId in valid_ids:
                return {"selection": res.model_dump(), "usedFallback": False}
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"opportunity_selector_graph LLM fallback: {type(exc).__name__}: {exc}")

    return {"selection": fallback, "usedFallback": True}


def build_opportunity_selector_graph():
    g = StateGraph(SelectorState)
    g.add_node("assess_risk_budget", _assess_risk_budget)
    g.add_node("llm_rank_and_pick", _llm_rank_and_pick)
    g.add_edge(START, "assess_risk_budget")
    g.add_edge("assess_risk_budget", "llm_rank_and_pick")
    g.add_edge("llm_rank_and_pick", END)
    return g.compile()


opportunity_selector_graph = build_opportunity_selector_graph()


# ───────────────────────── Graph 2: Position Trail & SL Pilot ─────────────────────────
class TrailState(TypedDict, total=False):
    tradeId: int
    contract: str
    traderCode: str
    riskLevel: str
    entryAt: float
    initialStop: float
    initialTarget: float
    currentStop: float
    currentTarget: float
    ltp: float
    peakPrice: float
    candles1m: list[dict[str, Any]]
    micro: dict[str, Any]
    decision: dict[str, Any]
    usedFallback: bool


async def _analyze_microstructure(state: TrailState) -> dict[str, Any]:
    micro = trader_brain.analyze_premium_candles(state.get("candles1m") or [], float(state["ltp"]))
    return {"micro": micro}


async def _llm_trail_decision(state: TrailState) -> dict[str, Any]:
    entry_at = float(state["entryAt"])
    init_stop = float(state["initialStop"])
    init_tgt = float(state["initialTarget"])
    cur_stop = float(state["currentStop"])
    cur_tgt = float(state["currentTarget"])
    ltp = float(state["ltp"])
    peak = float(state.get("peakPrice") or ltp)
    micro = state.get("micro") or {}

    brain_dec = trader_brain.evaluate(
        entry_at=entry_at,
        initial_stop=init_stop,
        initial_target=init_tgt,
        current_stop=cur_stop,
        current_target=cur_tgt,
        ltp=ltp,
        peak_price=peak,
        win_rate_pct=75.0,
        confidence=80,
        trader_profile="STEP_GUARD",
        trader_code=state.get("traderCode"),
        candles_1m=state.get("candles1m") or [],
    )
    mapped_action: Literal["HOLD", "TRAIL_SL", "STEP_TARGET", "EXIT_NOW"] = (
        "EXIT_NOW"
        if brain_dec.action == "EXIT"
        else "STEP_TARGET"
        if brain_dec.action in ("TRAIL_TARGET", "TRAIL_BOTH")
        else "TRAIL_SL"
        if brain_dec.action == "TRAIL_SL"
        else "HOLD"
    )
    fallback = {
        "action": mapped_action,
        "newStop": brain_dec.newStop,
        "newTarget": brain_dec.newTarget,
        "reasoning": brain_dec.reason,
    }

    try:
        if await _llm._resolve_healthy_url():
            playbook = _get_playbook(state.get("traderCode"))
            ist_time, ist_window = _ist_session_window()
            idx_note = _index_profile_note(state.get("contract"))
            prompt = (
                f"You are an institutional Indian 1m/3m options scalping & trailing SL pilot.\n"
                f"IST Clock: {ist_time} | Session Window: {ist_window}\n"
                f"Index Profile: {idx_note}\n"
                f"Time-Stop & Gamma Guard: If stalled 15-20m without expansion or spot crosses opposite VWAP, EXIT_NOW to avoid theta/Gamma trap.\n"
                f"Manager Mode: {playbook['title']}\n"
                f"Manager Trailing Psychology: {playbook['trailRule']}\n"
                f"Contract: {state.get('contract')} | Trader: {state.get('traderCode')} | Risk: {state.get('riskLevel', 'L2_BALANCED')}\n"
                f"Entry: ₹{entry_at:.2f} | Current SL: ₹{cur_stop:.2f} | Current Target: ₹{cur_tgt:.2f} | "
                f"Live LTP: ₹{ltp:.2f} | Peak: ₹{peak:.2f}\n"
                f"Microstructure: {micro}\n"
                f"Rules: Never lower SL below ₹{cur_stop:.2f}. If LTP > Entry + 50% of move, lock profit by raising SL. "
                f"If momentum is STRONG near Target, step Target higher and lock SL at prior target. "
                f"Decide action (HOLD, TRAIL_SL, STEP_TARGET, or EXIT_NOW), newStop, newTarget, and concise reasoning."
            )
            res: LlmTrailDecision = await _llm.generate_structured(
                prompt=prompt,
                schema=LlmTrailDecision,
                timeout=12.0,
            )
            return {"decision": res.model_dump(), "usedFallback": False}
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"position_trail_graph LLM fallback: {type(exc).__name__}: {exc}")

    return {"decision": fallback, "usedFallback": True}


async def _enforce_invariants(state: TrailState) -> dict[str, Any]:
    dec = dict(state.get("decision") or {})
    cur_stop = float(state["currentStop"])
    cur_tgt = float(state["currentTarget"])
    ltp = float(state["ltp"])

    # Hard safety invariant: Stop-Loss can NEVER move downward
    new_stop = trader_brain.round_tick(max(cur_stop, float(dec.get("newStop") or cur_stop)))
    if dec.get("action") != "EXIT_NOW" and new_stop >= ltp:
        new_stop = cur_stop
    new_tgt = trader_brain.round_tick(max(cur_tgt, float(dec.get("newTarget") or cur_tgt)))
    dec["newStop"] = new_stop
    dec["newTarget"] = new_tgt
    return {"decision": dec}


def build_position_trail_graph():
    g = StateGraph(TrailState)
    g.add_node("analyze_microstructure", _analyze_microstructure)
    g.add_node("llm_trail_decision", _llm_trail_decision)
    g.add_node("enforce_invariants", _enforce_invariants)
    g.add_edge(START, "analyze_microstructure")
    g.add_edge("analyze_microstructure", "llm_trail_decision")
    g.add_edge("llm_trail_decision", "enforce_invariants")
    g.add_edge("enforce_invariants", END)
    return g.compile()


position_trail_graph = build_position_trail_graph()

