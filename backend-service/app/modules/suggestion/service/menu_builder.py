import hashlib
import json
from typing import Any

from app.modules.suggestion.provider.underlying_config import UnderlyingConfig

MAX_SPREAD_PCT = 1.5  # scalping: the spread must not eat a 5-10% target
MIN_STOP_PCT = 2.5  # stops tighter than this get hit by normal option noise
VOLUME_CONFIRM_RATIO = 1.2  # latest candle volume vs recent average
VOLUME_DRY_RATIO = 0.6
VOLUME_BONUS = 6
MIN_OI = 1000


def direction_bias(research: dict[str, Any], market: dict[str, Any]) -> str:
    """Trend context BULLISH / BEARISH / NEUTRAL from research direction plus the day's price trend.
    It does not pick CALL or PUT: strategies and rules do that."""
    score = 0
    d = (research.get("direction") or "").upper()
    # Research direction leads (weight 2); the day's price trend breaks ties.
    score += 2 if d in ("BULLISH", "UP", "LONG") else -2 if d in ("BEARISH", "DOWN", "SHORT") else 0
    trend = (market.get("candles") or {}).get("trendPct", 0)
    score += 1 if trend > 0.15 else -1 if trend < -0.15 else 0
    return "BULLISH" if score > 0 else "BEARISH" if score < 0 else "NEUTRAL"


def volume_confirms(candles: dict[str, Any], side: str) -> bool:
    """Latest candle moves the same way as the contract AND trades on clearly above-average volume."""
    if not candles or candles.get("volumeRatio", 0) < VOLUME_CONFIRM_RATIO:
        return False
    return bool(candles.get("lastCandleUp")) == (side == "CE")


def volume_adjustment(candles: dict[str, Any], side: str) -> int:
    """+ points when volume confirms the move, - points when the market is dry (thin volume)."""
    if volume_confirms(candles, side):
        return VOLUME_BONUS
    if candles and 0 < candles.get("volumeRatio", 1) < VOLUME_DRY_RATIO:
        return -VOLUME_BONUS
    return 0


def brief_hash(brief: dict[str, Any]) -> str:
    """Stable hash of the rounded brief; unchanged hash => reuse the last AI answer."""
    return hashlib.sha256(json.dumps(brief, sort_keys=True, default=str).encode()).hexdigest()


def build_brief(cfg: UnderlyingConfig, research: dict[str, Any], market: dict[str, Any], bias: str) -> dict[str, Any]:
    step = cfg.strikeStep
    chains = []
    for c in market.get("chains", []):
        chains.append(
            {
                "expiry": c["expiry"],
                "pcr": round(c["pcr"], 1),
                "support": c.get("support"),
                "resistance": c.get("resistance"),
            }
        )
    return {
        "underlying": cfg.code,
        "spot": round(market["spot"] / step) * step,  # rounded so tiny ticks do not change the hash
        "bias": bias,
        "trendPct": round((market.get("candles") or {}).get("trendPct", 0), 1),
        "volumeRatio": round((market.get("candles") or {}).get("volumeRatio", 0), 1),  # latest candle vs average
        "lastCandle": "UP" if (market.get("candles") or {}).get("lastCandleUp") else "DOWN",
        "researchStatus": research.get("newsStatus"),
        "researchScore": research.get("score"),
        "thesis": (research.get("thesis") or "")[:300],
        "chains": chains,
    }


def build_menu(
    cfg: UnderlyingConfig,
    market: dict[str, Any],
    bias: str,
    min_margin: float,
    limit: int = 15,
    max_margin: float = 10.0,
    max_stop: float = 5.0,
) -> list[dict[str, Any]]:
    """Code builds executable contracts. The AI may only choose from this list."""
    # Trend is context only: both CALL and PUT stay on the menu. Strategies and rules decide the side,
    # so a bullish NIFTY can still carry a PUT opportunity (resistance rejection, reversal, ...).
    sides = ["CE", "PE"]
    spot = market["spot"]
    menu: list[dict[str, Any]] = []
    for ci, chain in enumerate(market.get("chains", [])):
        res: float | None = chain.get("resistance")
        sup: float | None = chain.get("support")
        atm_rows = sorted(chain["strikes"], key=lambda s: abs(s["strike"] - spot))[:7]
        for row in atm_rows:
            for side in sides:
                leg = row[side]
                ltp, bid, ask = leg["ltp"], leg["bid"], leg["ask"]
                if ltp <= 0 or leg["oi"] < MIN_OI or leg["volume"] <= 0:
                    continue
                spread = ((ask - bid) / ltp * 100) if ask and bid else 0.0
                if spread > MAX_SPREAD_PCT:
                    continue
                delta = abs(leg["delta"]) or 0.5
                # underlying move available toward the OI wall (target) and toward the opposite wall (stop)
                if side == "CE":
                    up = (res - spot) if res and res > spot else spot * 0.004
                    down = (spot - sup) if sup and sup < spot else spot * 0.003
                else:
                    up = (spot - sup) if sup and sup < spot else spot * 0.004
                    down = (res - spot) if res and res > spot else spot * 0.003
                # Small, frequent profits: target a 5-10% premium gain, never more than the room to the OI wall.
                room_pct = delta * up * 0.8 / ltp * 100
                target_pct = min(max_margin, room_pct)
                if target_pct < min_margin:
                    continue  # not enough room for even the smallest target
                structural_stop_pct = delta * down * 0.5 / ltp * 100
                stop_pct = max(MIN_STOP_PCT, min(max_stop, target_pct / 2, structural_stop_pct or max_stop))
                target = round(ltp * (1 + target_pct / 100), 2)
                stop = round(ltp * (1 - stop_pct / 100), 2)
                margin = (target - ltp) / ltp * 100
                rr = target_pct / stop_pct
                if spread > margin / 4:
                    continue  # spread cost must stay well below the target
                if rr < 1.2:
                    continue
                menu.append(
                    {
                        "id": f"{cfg.code}-{chain['expiry']}-{int(row['strike'])}-{side}",
                        "underlying": cfg.code,
                        "instrumentKey": leg["key"],
                        "side": side,
                        "volumeConfirmed": volume_confirms(market.get("candles") or {}, side),
                        "withTrend": bias == "NEUTRAL" or (side == "CE") == (bias == "BULLISH"),
                        "strike": row["strike"],
                        "expiry": chain["expiry"],
                        "expiryRank": "CURRENT" if ci == 0 else "NEXT",
                        "entry": round(ltp, 2),
                        "stop": stop,
                        "target": target,
                        "marginPct": round(margin, 1),
                        "stopPct": round(stop_pct, 1),
                        "delta": round(delta, 2),
                        "rewardRisk": round(rr, 2),
                        "spreadPct": round(spread, 1),
                        "oi": int(leg["oi"]),
                    }
                )
    menu.sort(key=lambda m: (m["rewardRisk"], m["oi"]), reverse=True)
    # keep both sides visible to the AI: best contracts of each side first, then fill by quality
    per_side = max(1, limit // 2)
    chosen = [m for side in sides for m in [x for x in menu if x["side"] == side][:per_side]]
    rest = [m for m in menu if m not in chosen]
    chosen = (chosen + rest)[:limit]
    chosen.sort(key=lambda m: (m["rewardRisk"], m["oi"]), reverse=True)
    return chosen


def baseline_pick(menu: list[dict[str, Any]], bias: str) -> list[dict[str, Any]]:
    """Code-only ranking: used for comparison and as fallback when the AI is down or invalid."""
    out = []
    for m in menu:
        conf = int(min(95, 50 + m["rewardRisk"] * 10 + (8 if m["withTrend"] and bias != "NEUTRAL" else 0) + (VOLUME_BONUS if m["volumeConfirmed"] else 0) + (4 if 0.4 <= m["delta"] <= 0.65 else 0) - m["spreadPct"]))
        out.append({"id": m["id"], "confidence": conf, "strategy": "baseline-rr", "reasons": [
            f"reward/risk {m['rewardRisk']}", f"margin {m['marginPct']}%"], "risks": ["code-only ranking"]})
    out.sort(key=lambda p: p["confidence"], reverse=True)
    return out


def expected_edge_pct(confidence: int, target_pct: float, stop_pct: float) -> float:
    """Average premium % gained per trade if `confidence` is the chance of hitting target before stop."""
    p = max(0.0, min(1.0, confidence / 100.0))
    return round(p * target_pct - (1 - p) * stop_pct, 2)
