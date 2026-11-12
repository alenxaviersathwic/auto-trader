"""
PAPER trading of the expiry-day iron fly on LIVE quotes (research roadmap days 61-90: "paper-trade surviving
archetypes on live quotes"). No orders are ever sent. Every minute during the session (iron_fly_paper_job):

  * for each underlying whose own series expires today, with no paper fly yet today: check iron_fly.eligible()
    on live data and, if it passes, iron_fly.build() from the live chain (sells at bids, buys at asks) -> OPEN
  * for an open paper fly: mark it to the live chain (shorts bought back at the ask, wings sold at the bid) and close
    it on iron_fly.check_exit() -> CLOSED with net rupees after all 8 orders' charges

Ledger: backtest_out/paper_iron_fly.jsonl (append-only events; one line per OPEN / MARK / CLOSE). scripts/edge_report.py
reads the CLOSE lines, so after ~200 expiries the archetype gets a real promotion_verdict().
"""
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config.settings import settings
from app.core.db.session import async_session_factory
from app.core.logging.logger import logger
from app.modules.opportunities.provider.underlying_config import get_config, is_market_open
from app.modules.opportunities.provider.upstox_market_data import market_data
from app.modules.opportunities.service import iron_fly as fly
from app.modules.opportunities.service.day_context import compute_calendar_tags

_IST = ZoneInfo("Asia/Kolkata")
LEDGER = Path(__file__).resolve().parents[4] / "backtest_out" / "paper_iron_fly.jsonl"
CODES = ("NIFTY", "SENSEX")  # the two weekly series; monthlies expire once a month and add few samples


def _events(day: str) -> list[dict[str, Any]]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("day") == day:
            out.append(e)
    return out


def _append(e: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a") as fh:
        fh.write(json.dumps(e, default=str) + "\n")


def _gap_pct(market: dict[str, Any], today: str) -> float | None:
    bars, daily = market.get("spotBars1m") or [], market.get("daily") or []
    prev = [d for d in daily if str(d.get("t", ""))[:10] < today]
    if not bars or not prev:
        return None
    pdc = prev[-1]["c"]
    return round((bars[0]["o"] - pdc) / pdc * 100, 2) if pdc else None


def _atm_iv(chain: dict[str, Any], spot: float) -> float | None:
    rows = chain.get("strikes") or []
    if not rows:
        return None
    a = min(rows, key=lambda r: abs(float(r["strike"]) - spot))
    ivs = [x for x in ((a.get("CE") or {}).get("iv"), (a.get("PE") or {}).get("iv")) if x]
    return sum(ivs) / len(ivs) if ivs else None


def _quotes(chain: dict[str, Any]) -> dict[tuple[str, float], dict[str, float]]:
    return {(sd, float(r["strike"])): r[sd] for r in chain.get("strikes") or [] for sd in ("CE", "PE")}


def _rebuild(e: dict[str, Any]) -> fly.IronFly:
    d = dict(e["fly"])
    d["legs"] = tuple(tuple(x) for x in d["legs"])
    return fly.IronFly(**d)


async def tick(now: datetime | None = None) -> list[str]:
    now = (now or datetime.now(UTC)).astimezone(_IST)
    day = now.date().isoformat()
    notes: list[str] = []
    events = _events(day)
    for code in CODES:
        cfg = get_config(code)
        if not is_market_open(cfg, now):
            continue
        mine = [e for e in events if e.get("code") == code]
        opened = next((e for e in mine if e["kind"] == "OPEN"), None)
        closed = any(e["kind"] == "CLOSE" for e in mine)
        if closed:
            continue
        try:
            async with async_session_factory() as s:
                market = await market_data.fetch(cfg, s)
        except Exception as ex:  # noqa: BLE001
            notes.append(f"{code}: no market data ({type(ex).__name__})")
            continue
        chain = next((c for c in market.get("chains") or [] if c.get("expiry") == day), None)
        if opened is None:
            if chain is None:
                continue  # not this underlying's expiry day
            gap = _gap_pct(market, day)
            prior = [d for d in market.get("daily") or [] if str(d.get("t", ""))[:10] < day]
            vrp = fly.vrp_ratio(_atm_iv(chain, market["spot"]), prior)
            try:
                async with async_session_factory() as s:
                    vix_hist = await market_data.vix_history(s)
            except Exception:  # noqa: BLE001 -- unknown percentile = gate fails closed
                vix_hist = []
            vix_now = (market.get("vix") or {}).get("value")
            from app.modules.opportunities.graph import nodes  # lazy: sticky day bias lives in the graph module

            bias = ((nodes._day_bias.get(code) or {}).get("state") or {}).get("bias")
            try:  # route N1: implied expiry move vs realised range of past same-weekday expiry days (~6 months daily)
                async with async_session_factory() as s:
                    hist = await market_data.historical_daily(cfg, s, years=1)
                wd = now.weekday()
                past = [b["h"] - b["l"] for b in hist if str(b.get("t", ""))[:10] < day
                        and datetime.fromisoformat(str(b["t"])[:10]).weekday() == wd]
            except Exception:  # noqa: BLE001 -- unknown = this route fails closed, the VRP route still decides
                past = []
            atm_row = min(chain.get("strikes") or [{}], key=lambda r: abs(r.get("strike", 0) - market["spot"]))
            straddle = ((atm_row.get("CE") or {}).get("bid") or 0) + ((atm_row.get("PE") or {}).get("bid") or 0)
            a = {"dte": 0, "levels": {"gapPct": gap}, "vix": market.get("vix") or {}, "dayBias": bias,
                 "vrpRatio": vrp, "vixPctile": fly.percentile(vix_now, vix_hist),
                 "impliedMoveRatio": fly.implied_move_ratio(straddle, past),
                 "noise": nodes._last_noise.get(code) or {}}
            ok, why = fly.eligible(a, now, compute_calendar_tags(now, cfg.exchange))
            g = nodes._last_gamma.get(code) or {}
            if g.get("enabled") and (g.get("route") or {}).get("shortPremium") is False:
                ok, why = False, why + [f"dealer gamma {g.get('regime')}: no short premium"]
            if not ok:
                if now.time() > fly.ENTRY_TO and not any(e["kind"] == "SKIP" for e in mine):
                    _append({"day": day, "code": code, "kind": "SKIP", "at": now.isoformat(), "why": why})
                continue
            centre = market["spot"]
            pos_bias = (nodes._positioning.get("state") or {}).get("bias") or 0
            if settings.POSITIONING_OVERLAY_ENABLED and pos_bias:
                centre += pos_bias * cfg.strikeStep  # review Strategy 4: centre the fly one strike toward FII bias
            f, why_b = fly.build(chain, centre, cfg.strikeStep, int(market.get("lotUnits") or cfg.lotSize),
                                 code, cfg.exchange, gap)
            if f is None:
                notes.append(f"{code}: no fly ({why_b})")
                continue
            _append({"day": day, "code": code, "kind": "OPEN", "at": now.isoformat(), "spot": market["spot"],
                     "gapPct": gap, "vrpRatio": vrp, "vixPctile": a["vixPctile"], "fly": f.as_dict()})
            notes.append(f"{code}: PAPER OPEN fly {f.putWing:.0f}/{f.atm:.0f}/{f.callWing:.0f} credit {f.credit}")
            continue
        f = _rebuild(opened)
        q = _quotes(chain) if chain else {}
        px = {}
        for act, sd, k, _p, _key in f.legs:
            leg = q.get((sd, float(k)))
            if leg:
                px[(sd, float(k))] = (leg.get("ask") if act == "SELL" else leg.get("bid")) or 0
        if len(px) < 4 or any(v <= 0 for v in px.values()):
            continue
        val = round(fly.fly_value(px, f), 2)
        bars1 = market.get("spotBars1m") or []
        last5 = bars1[(len(bars1) // 5) * 5 - 1]["c"] if len(bars1) >= 5 else None  # last COMPLETED 5-min close
        reason = fly.check_exit(f, val, now, last5)
        if reason:
            pnl = fly.pnl_rs(f, val)
            _append({"day": day, "code": code, "kind": "CLOSE", "at": now.isoformat(), "reason": reason,
                     "exitValue": val, "net": pnl, "strategy": "IRON_FLY", "side": "FLY"})
            notes.append(f"{code}: PAPER CLOSE {reason} value {val} net Rs {pnl:+,.0f}")
        else:
            _append({"day": day, "code": code, "kind": "MARK", "at": now.isoformat(), "value": val})
    if notes:
        logger.info(f"[IRON_FLY_PAPER] {' | '.join(notes)}")
    return notes
