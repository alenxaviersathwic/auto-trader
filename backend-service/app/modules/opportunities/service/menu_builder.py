import hashlib
import json
from datetime import datetime, time as dtime
from typing import Any
from zoneinfo import ZoneInfo

from app.modules.opportunities.provider.underlying_config import UnderlyingConfig
from app.modules.opportunities.service.costs import round_trip_cost_pct

MAX_SPREAD_PCT = 1.5  # scalping: the spread must not eat a 5-10% target
MIN_STOP_PCT = 2.5  # stops tighter than this get hit by normal option noise
VOLUME_BONUS = 6
SETUP_BONUS = 4  # confidence points per setup strength step above 2
MIN_OI = 1000
# MCX option OI is far smaller than NIFTY/BANKNIFTY (one lot is much larger notional), so an index-tuned
# 1000-contract floor and 1.5% spread cap filtered every commodity contract out of the menu.
MIN_OI_COMMODITY = 150
MAX_SPREAD_PCT_COMMODITY = 3.0
_IST = ZoneInfo("Asia/Kolkata")
# G-EXP-GAMMA: no new positions in a same-day-expiring (0DTE) series after 13:30 IST.
EXPIRY_GAMMA_CUTOFF = dtime(13, 30)


def _liquidity_thresholds(cfg: UnderlyingConfig) -> tuple[float, int]:
    if cfg.type == "COMMODITY":
        return MAX_SPREAD_PCT_COMMODITY, MIN_OI_COMMODITY
    return MAX_SPREAD_PCT, MIN_OI


def _is_0dte_blocked(expiry: str, now: datetime | None = None) -> bool:
    now = now or datetime.now(_IST)
    return expiry == now.strftime("%Y-%m-%d") and now.time() >= EXPIRY_GAMMA_CUTOFF


def direction_bias(research: dict[str, Any], analysis: dict[str, Any]) -> str:
    """Trend context BULLISH / BEARISH / NEUTRAL: research direction (weight 2) + 15-minute trend + futures VWAP.
    Context only: the side comes from setups and strategies."""
    score = 0
    d = (research.get("direction") or "").upper()
    score += 2 if d in ("BULLISH", "UP", "LONG") else -2 if d in ("BEARISH", "DOWN", "SHORT") else 0
    t = analysis.get("trend15")
    score += 1 if t == "UP" else -1 if t == "DOWN" else 0
    vw = analysis.get("vwap")
    if vw:
        score += 1 if vw["above"] else -1
    return "BULLISH" if score > 0 else "BEARISH" if score < 0 else "NEUTRAL"


def volume_confirms(analysis: dict[str, Any], side: str) -> bool:
    v = analysis.get("volume") or {}
    return bool(v.get("spike")) and bool(v.get("lastBarUp")) == (side == "CE")


def volume_adjustment(analysis: dict[str, Any], side: str) -> int:
    if volume_confirms(analysis, side):
        return VOLUME_BONUS
    if (analysis.get("volume") or {}).get("dry"):
        return -VOLUME_BONUS
    return 0


def setup_adjustment(setups: list[dict[str, Any]], side: str) -> tuple[int, dict[str, Any] | None]:
    """Confidence points from the best coded setup on this side (a conflicting setup earns none)."""
    best = next((s for s in setups if s["side"] == side), None)
    if not best:
        return 0, None
    return (0 if best.get("conflict") else max(0, best["strength"] - 1) * SETUP_BONUS), best


def buildup_adjustment(analysis: dict[str, Any], side: str) -> int:
    bu = (analysis.get("buildup") or {}).get("state")
    ce = side == "CE"
    if bu in (("SHORT_BUILDUP", "LONG_UNWINDING") if ce else ("LONG_BUILDUP", "SHORT_COVERING")):
        return -8
    if bu in (("LONG_BUILDUP", "SHORT_COVERING") if ce else ("SHORT_BUILDUP", "LONG_UNWINDING")):
        return 4
    return 0


TAG_BONUS = 5


def tag_adjustment(day_tags: list[str], strategy_tags: dict[str, list[str]], cited_strategy: str | None) -> tuple[int, list[str]]:
    """Small confidence nudge when the pick's cited strategy is tagged for today's conditions
    (e.g. a strategy tagged AFTER_HOLIDAY gets a bonus the morning after a trading holiday).
    Matching is case-insensitive substring, same as the against-trend strategy-citation check
    in validate() -- the AI doesn't always echo a strategy name byte-for-byte."""
    if not cited_strategy or not day_tags or not strategy_tags:
        return 0, []
    cited = cited_strategy.lower()
    for name, tags in strategy_tags.items():
        if not tags:
            continue
        if name.lower() in cited or cited in name.lower():
            matched = [t for t in tags if t in day_tags]
            if matched:
                return TAG_BONUS, matched
    return 0, []


def strategy_stop_loss_for_pick(
    strategy_stop_loss: dict[str, float] | None,
    cited_strategy: str | None,
) -> tuple[float | None, str | None]:
    """Resolve the stop-loss % configured/calibrated on Strategy Master for the cited strategy."""
    if not strategy_stop_loss:
        return None, None
    if cited_strategy:
        cited = cited_strategy.lower()
        for name, sl_pct in strategy_stop_loss.items():
            if name.lower() in cited or cited in name.lower():
                return float(sl_pct), name
    # Fallback to mean stopLossPct across active suggestable strategies for this underlying
    vals = [float(v) for v in strategy_stop_loss.values() if v and v > 0]
    if vals:
        return round(sum(vals) / len(vals), 2), "Strategy Master Win-Rate Profile"
    return None, None


def brief_hash(brief: dict[str, Any]) -> str:
    """Stable hash of the rounded brief; unchanged hash => reuse the last AI answer."""
    return hashlib.sha256(json.dumps(brief, sort_keys=True, default=str).encode()).hexdigest()


def build_brief(cfg: UnderlyingConfig, research: dict[str, Any], market: dict[str, Any], bias: str,
                analysis: dict[str, Any], setups: list[dict[str, Any]], day_tags: list[str] | None = None,
                strategy_tags: dict[str, list[str]] | None = None) -> dict[str, Any]:
    q = cfg.strikeStep / 10

    def r(x: Any) -> Any:
        return round(round(float(x) / q) * q, 2) if isinstance(x, (int, float)) and x else x

    lv = analysis.get("levels") or {}
    vw = analysis.get("vwap") or {}
    vol = analysis.get("volume") or {}
    return {
        "underlying": cfg.code,
        "spot": r(market["spot"]),
        "bias": bias,
        "regime": analysis.get("regime"),
        "window": analysis["session"]["window"],
        "trend15m": analysis.get("trend15"),
        "aboveFuturesVwap": vw.get("above"),
        "vwapDistPct": round(vw.get("distPct", 0), 2) if vw else None,
        "volume5mRatio": round(vol.get("ratio5m", 0), 1) if vol else None,
        "futuresBuildup": (analysis.get("buildup") or {}).get("state"),
        "levels": {k: r(lv.get(k)) for k in ("pdh", "pdl", "pdc", "orHigh", "orLow", "tc", "bc", "dayHigh", "dayLow")
                   if lv.get(k)},
        "cpr": "NARROW" if lv.get("cprNarrow") else "WIDE" if lv.get("cprWide") else "NORMAL",
        "gapPct": lv.get("gapPct"),
        "dayRangeVsAtrPct": analysis.get("rangeUsedPct"),
        "expectedMovePct": analysis.get("expectedMovePct"),
        "vix": analysis.get("vix"),
        "setups": [
            {"name": s["name"], "side": s["side"], "strength": s["strength"], "why": s["reason"],
             "target": r(s["target"]), "stop": r(s["stop"]), "conflict": s.get("conflict"),
             "entry1m": r(s.get("entry1m")), "trigger1m": r(s.get("trigger1m")), "ema1m": r(s.get("ema1m"))}
            for s in setups
        ],
        "researchStatus": research.get("newsStatus"),
        "researchScore": research.get("score"),
        "thesis": (research.get("thesis") or "")[:300],
        "chains": [
            {"expiry": c["expiry"], "pcr": round(c["pcr"], 1), "support": c.get("support"), "resistance": c.get("resistance")}
            for c in market.get("chains", [])
        ],
        "dayTags": day_tags or [],
        # Only strategies that are themselves tagged for today's conditions -- a hint to the AI,
        # not a hard filter. There is no separate day-of-week eligibility gate: every suggestable
        # strategy is a candidate every day, and tag matches here just nudge confidence (see
        # tag_adjustment() below).
        "tagMatchedStrategies": [
            name for name, tags in (strategy_tags or {}).items() if any(t in (day_tags or []) for t in tags)
        ],
    }


def build_menu(
    cfg: UnderlyingConfig,
    market: dict[str, Any],
    bias: str,
    min_margin: float,
    limit: int = 15,
    max_margin: float = 10.0,
    max_stop: float = 5.0,
    reasons: dict[str, int] | None = None,
    setups: list[dict[str, Any]] | None = None,
    require_setup: bool = False,
    atm_itm_only: bool = False,
    min_delta: float = 0.0,
) -> list[dict[str, Any]]:
    """Code builds executable contracts.

    require_setup  only contracts on the side of a validated setup are listed (the AI just ranks them).
    atm_itm_only   only the ATM strike and the one strike in-the-money (lower for CE, higher for PE).
    min_delta      contracts with |delta| below this are dropped (a quoted delta of 0 is treated as missing).
 The AI may only choose from this list.

    With a coded setup on a side, the contract's premium target/stop come from the setup's chart levels
    (next key level / invalidation) through the contract delta. Without one, the OI walls give the room.
    If `reasons` is passed, it is filled with a count of why each candidate was dropped."""
    drop = reasons if reasons is not None else {}
    setups = setups or []

    def _d(k: str) -> None:
        drop[k] = drop.get(k, 0) + 1

    sides = ["CE", "PE"]
    spot = market["spot"]
    lot = int(market.get("lotUnits") or cfg.lotSize)
    best_setup = {side: next((s for s in setups if s["side"] == side and not s.get("conflict")), None) for side in sides}
    menu: list[dict[str, Any]] = []
    max_spread_pct, min_oi = _liquidity_thresholds(cfg)
    for ci, chain in enumerate(market.get("chains", [])):
        if _is_0dte_blocked(chain["expiry"]):
            _d("expiry-day after 13:30")
            continue
        res: float | None = chain.get("resistance")
        sup: float | None = chain.get("support")
        atm_rows = sorted(chain["strikes"], key=lambda s: abs(s["strike"] - spot))[:9]
        by_strike = sorted(chain["strikes"], key=lambda s: s["strike"])
        atm_strike = min(by_strike, key=lambda s: abs(s["strike"] - spot))["strike"] if by_strike else None
        allowed: dict[str, set[float]] = {"CE": set(), "PE": set()}
        if atm_strike is not None:
            i = next(k for k, r in enumerate(by_strike) if r["strike"] == atm_strike)
            allowed["CE"] = {atm_strike} | ({by_strike[i - 1]["strike"]} if i > 0 else set())
            allowed["PE"] = {atm_strike} | ({by_strike[i + 1]["strike"]} if i + 1 < len(by_strike) else set())
        for row in atm_rows:
            for side in sides:
                if require_setup and not best_setup[side]:
                    continue  # no validated setup on this side: nothing to rank
                if atm_itm_only and row["strike"] not in allowed[side]:
                    continue
                leg = row[side]
                ltp, bid, ask = leg["ltp"], leg["bid"], leg["ask"]
                if ltp <= 0:
                    _d("no price")
                    continue
                if leg["oi"] < min_oi:
                    _d(f"OI<{min_oi}")
                    continue
                if leg["volume"] <= 0:
                    _d("no volume today")
                    continue
                spread = ((ask - bid) / ltp * 100) if ask and bid else 0.0
                if spread > max_spread_pct:
                    _d(f"spread>{max_spread_pct}%")
                    continue
                if min_delta and leg["delta"] and abs(leg["delta"]) < min_delta:
                    _d(f"delta<{min_delta}")
                    continue
                delta = abs(leg["delta"]) or 0.5
                setup = best_setup[side]
                if setup:
                    up = (setup["target"] - spot) if side == "CE" else (spot - setup["target"])
                    down = (spot - setup["stop"]) if side == "CE" else (setup["stop"] - spot)
                    if up <= 0 or down <= 0:
                        setup = None  # price already ran past the plan: treat as no setup
                        if require_setup:
                            _d("price ran past setup plan")
                            continue
                min_stop_floor = min(MIN_STOP_PCT, max_stop)
                if setup:
                    target_pct = min(max_margin, delta * up * 0.9 / ltp * 100)
                    # The chart invalidation is usually much wider than a 2.5-5% premium stop (5% of a Rs 120
                    # NIFTY option is ~12 index points). Strategy stop-loss % caps the premium risk; the chart level is reported.
                    chart_stop_pct = delta * down / ltp * 100
                    stop_pct = max(min_stop_floor, min(max_stop, chart_stop_pct))
                else:
                    if side == "CE":
                        up = (res - spot) if res and res > spot else spot * 0.004
                        down = (spot - sup) if sup and sup < spot else spot * 0.003
                    else:
                        up = (spot - sup) if sup and sup < spot else spot * 0.004
                        down = (res - spot) if res and res > spot else spot * 0.003
                    target_pct = min(max_margin, delta * up * 0.8 / ltp * 100)
                    structural = delta * down * 0.5 / ltp * 100
                    stop_pct = max(min_stop_floor, min(max_stop, target_pct / 2, structural or max_stop))
                if target_pct < min_margin:
                    _d("no room for min target")
                    continue
                target = round(ltp * (1 + target_pct / 100), 2)
                stop = round(ltp * (1 - stop_pct / 100), 2)
                margin = (target - ltp) / ltp * 100
                rr = target_pct / stop_pct
                if spread > margin / 4:
                    _d("spread eats target")
                    continue
                if rr < 1.2:
                    _d("reward:risk<1.2")
                    continue
                cost = round_trip_cost_pct(ltp, lot, cfg.exchange, margin)
                menu.append(
                    {
                        "id": f"{cfg.code}-{chain['expiry']}-{int(row['strike'])}-{side}",
                        "underlying": cfg.code,
                        "instrumentKey": leg["key"],
                        "side": side,
                        "setup": setup["name"] if setup else None,
                        "setupStrength": setup["strength"] if setup else 0,
                        "chartStop": setup["stop"] if setup else None,
                        "chartTarget": setup["target"] if setup else None,
                        "volumeConfirmed": False,  # filled by the node from the analysis
                        "withTrend": bias == "NEUTRAL" or (side == "CE") == (bias == "BULLISH"),
                        "strike": row["strike"],
                        "expiry": chain["expiry"],
                        "expiryRank": "CURRENT" if ci == 0 else "NEXT",
                        "entry": round(ltp, 2),
                        "stop": stop,
                        "target": target,
                        "marginPct": round(margin, 1),
                        "stopPct": round(stop_pct, 1),
                        "costPct": cost,
                        "delta": round(delta, 2),
                        "rewardRisk": round(rr, 2),
                        "spreadPct": round(spread, 1),
                        "oi": int(leg["oi"]),
                        "lotUnits": lot,
                    }
                )
    menu.sort(key=lambda m: (m["setupStrength"], m["rewardRisk"], m["oi"]), reverse=True)
    per_side = max(1, limit // 2)
    chosen = [m for side in sides for m in [x for x in menu if x["side"] == side][:per_side]]
    rest = [m for m in menu if m not in chosen]
    chosen = (chosen + rest)[:limit]
    chosen.sort(key=lambda m: (m["setupStrength"], m["rewardRisk"], m["oi"]), reverse=True)
    return chosen


def baseline_pick(menu: list[dict[str, Any]], bias: str) -> list[dict[str, Any]]:
    """Code-only ranking, used when the AI is down or invalid. Deliberately modest: without a coded setup a
    reward:risk ranking is not evidence, so such picks usually stay under the confidence bar."""
    out = []
    for m in menu:
        strength = m.get("setupStrength", 0)
        conf = int(min(80, 40 + m["rewardRisk"] * 5 + strength * 4 + (0 if strength else -8)
                       + (4 if m["withTrend"] and bias != "NEUTRAL" else 0)
                       + (4 if m["volumeConfirmed"] else 0)
                       + (3 if 0.4 <= m["delta"] <= 0.65 else 0) - 2 * m["spreadPct"]))
        why = [f"reward/risk {m['rewardRisk']}", f"margin {m['marginPct']}%"]
        if m.get("setup"):
            why.insert(0, f"setup {m['setup']} (strength {strength})")
        out.append({"id": m["id"], "confidence": conf, "strategy": m.get("setup") or "baseline-rr", "reasons": why,
                    "risks": ["code-only ranking (AI unavailable)"]})
    out.sort(key=lambda p: p["confidence"], reverse=True)
    return out


def expected_edge_pct(confidence: int, target_pct: float, stop_pct: float, cost_pct: float = 0.0) -> float:
    """Average premium % gained per trade AFTER charges, if `confidence` is the chance of target before stop."""
    p = max(0.0, min(1.0, confidence / 100.0))
    return round(p * target_pct - (1 - p) * stop_pct - cost_pct, 2)
