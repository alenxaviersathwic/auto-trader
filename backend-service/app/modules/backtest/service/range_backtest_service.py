"""
Range backtest: pick a FROM and TO date + indices; fetch the data from Upstox (1-minute index candles, daily candles
for the trend / 50-day / 5-day-swing inputs, India VIX) and NSE participant OI (FII_OPEN_DRIVE), then replay the
SAME code the live opportunities loop runs, minute by minute:

  market_analysis.analyze -> setups.detect (+ fii_open.signal) -> setups.confirm_timeframes (setup policy +
  institutional filters from settings.INSTITUTIONAL_FILTERS) -> guardrails.apply -> menu_builder.strike_mode
  -> premium_sim.simulate_momo (live MOMO exit: breakeven +1.5R, trail 2R from +2R, no fixed target)

Reported: trades, wins, P&L per index / per strategy / per day, and RULE IMPACT -- every signal a rule blocked is
also simulated as if it had been taken ("what the rule saved or cost"), and every setup the policy keeps switched
off is simulated the same way ("what that strategy would have made"). A portfolio pass applies the session rules
(one index position at a time, MAX lots the equity pays for -- or the live 1-lot risk sizer -- and the daily
max loss) for the capital entered.

Premiums are Black-Scholes at a fixed IV off the REAL index path (premium_sim.py): the entries, filters and exits
are the live ones; rupee P&L is an estimate.
"""
from __future__ import annotations

import asyncio
import re
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config.settings import settings
from app.core.db.session import async_session_factory
from app.core.exception.app_exceptions import BadRequestException, ConflictException
from app.core.logging.logger import logger
from app.modules.backtest.service import expiry_calendar, premium_sim
from app.modules.opportunities.provider.underlying_config import get_config
from app.modules.opportunities.provider.upstox_market_data import VIX_KEY, market_data
from app.modules.opportunities.service import day_type, fii_open, guardrails, positioning
from app.modules.opportunities.service import menu_builder as mb
from app.modules.opportunities.service import setups as su
from app.modules.opportunities.service.market_analysis import _bar_min, _mins, analyze
from app.modules.sessions.service.session_sizing import one_lot_risk_pct

IST = ZoneInfo("Asia/Kolkata")
MAX_RANGE_DAYS = 95
DAILY_LOOKBACK_DAYS = 120  # calendar days of daily candles before FROM: >= 50 sessions for DMA50
WARMUP_MIN, TAIL_MIN = 6, 20
SPLIT_NOTE = "first half / second half of the range: an edge should hold in both"
_jobs: dict[str, dict[str, Any]] = {}  # single uvicorn worker: in-memory job store


# ───────────────────────── helpers ─────────────────────────
def _by_day(bars: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in bars:
        out[b["t"][:10]].append(b)
    return dict(out)


def _rule_of(reason: str) -> str:
    """Stable rule name for a rejection reason: 'TREND_5_20: ...' -> TREND_5_20, policy / timeframe text -> a label."""
    m = re.match(r"^([A-Z][A-Z0-9_]+):", reason)
    if m:
        return m.group(1)
    r = reason.lower()
    for key, label in (("dropped", "POLICY: setup switched off"), ("short-premium", "POLICY: short-premium only"),
                       ("only inside an active", "POLICY: needs noise breakout"), ("15-min", "15-MIN TREND"),
                       ("1-min", "1-MIN CHART"), ("ema", "1-MIN CHART"), ("chasing", "1-MIN CHASE"),
                       ("gap", "UNFILLED GAP"), (" day", "DAY TYPE"), ("bias", "DAY TYPE"), ("late", "LATE WINDOW")):
        if key in r:
            return label
    return re.sub(r"[\d.,+\-%]+", "#", reason)[:48]


def _stats(pnls: list[float]) -> dict[str, Any]:
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    loss = [p for p in pnls if p <= 0]
    gl = -sum(loss)
    return {"trades": n, "wins": len(wins), "losses": len(loss),
            "winRatePct": round(len(wins) / n * 100, 1) if n else None,
            "netPnl": round(sum(pnls), 2), "avgPnl": round(sum(pnls) / n, 2) if n else None,
            "profitFactor": round(sum(wins) / gl, 2) if gl > 0 else None,
            "best": round(max(pnls), 2) if n else None, "worst": round(min(pnls), 2) if n else None}


def _drawdown(pnls: list[float]) -> float:
    eq = pk = dd = 0.0
    for p in pnls:
        eq += p
        pk = max(pk, eq)
        dd = max(dd, pk - eq)
    return round(dd, 2)


# ───────────────────────── data ─────────────────────────
async def _fetch(codes: list[str], d0: date, d1: date, progress) -> dict[str, Any]:
    data: dict[str, Any] = {"spot": {}, "daily": {}, "vix1m": {}, "vixDaily": []}
    async with async_session_factory() as s:
        for i, code in enumerate(codes):
            cfg = get_config(code)
            progress(f"fetching {code} 1-minute candles from Upstox", 2 + 18 * i / max(1, len(codes)))
            data["spot"][code] = _by_day(await market_data.history_span(cfg.instrumentKey, "minutes/1",
                                                                          d0.isoformat(), d1.isoformat(), s))
            data["daily"][code] = await market_data.history_span(
                cfg.instrumentKey, "days/1", (d0 - timedelta(days=DAILY_LOOKBACK_DAYS)).isoformat(), d1.isoformat(), s,
                chunk_days=3650)
        progress("fetching India VIX", 20)
        try:
            data["vix1m"] = _by_day(await market_data.history_span(VIX_KEY, "minutes/1", d0.isoformat(), d1.isoformat(), s))
            data["vixDaily"] = await market_data.history_span(VIX_KEY, "days/1", (d0 - timedelta(days=10)).isoformat(),
                                                              d1.isoformat(), s, chunk_days=3650)
        except Exception as e:  # noqa: BLE001 -- VIX only feeds PE_EXTRA; unknown inputs never veto
            logger.warning(f"[RANGE_BACKTEST] VIX unavailable: {type(e).__name__}: {e}")
    progress("fetching NSE participant OI (FII positioning)", 22)
    d = d0 - timedelta(days=10)
    while d <= d1:
        if d.weekday() < 5:
            await positioning.fetch(d)
        d += timedelta(days=1)
    return data


# ───────────────────────── one index x one day ─────────────────────────
def _replay_day(code: str, day: str, bars: list[dict[str, Any]], daily: list[dict[str, Any]],
                vix_prev: float | None, vix_min: list[dict[str, Any]]) -> dict[str, Any]:
    cfg = get_config(code)
    as_of = date.fromisoformat(day)
    cur = expiry_calendar.expiry_for(code, as_of)
    nxt = expiry_calendar.expiry_for(code, cur + timedelta(days=1)) if cur else None
    if not cur:
        return {"error": "no expiry calendar for this index"}
    dte_cur, dte_next = (cur - as_of).days, ((nxt or cur) - as_of).days
    open_m = _mins(cfg.open)
    close_m = _mins(cfg.close_today(datetime(as_of.year, as_of.month, as_of.day, 12, tzinfo=IST)))
    prior = [b for b in daily if b["t"][:10] < day]
    fii = fii_open.fii_net_change(as_of)
    vm = {_bar_min(b["t"]): b["c"] for b in vix_min}
    bm = lambda b: _bar_min(b["t"])  # noqa: E731

    trades: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    rows: list[Any] = []
    busy = -1
    cf_last: dict[tuple[str, str], int] = {}
    bias_state: dict[str, Any] = {}
    last_vix = None

    def cf(s: dict[str, Any], k: int, atr5: float, rule: str, m: int) -> None:
        key = (s["name"], s["side"])
        if k <= cf_last.get(key, -1):
            return  # the same setup/side "what-if" trade is still open: no overlapping copies
        r = premium_sim.simulate_momo(cfg, bars, k, s["side"], s["stop"], atr5, dte_next, bm,
                                      fixed_stop=bool(s.get("fixedStop")), close_min=close_m)
        if r:
            cf_last[key] = r.exitIdx
            blocked.append({"time": f"{m // 60:02d}:{m % 60:02d}", "setup": s["name"], "side": s["side"], "rule": rule,
                            "netPnl": r.netPnl, "outcome": r.outcome})

    for k in range(1, len(bars)):
        m = bm(bars[k])
        if m < open_m + WARMUP_MIN:
            continue
        if m > close_m - TAIL_MIN:
            break
        now = datetime(as_of.year, as_of.month, as_of.day, m // 60, m % 60, tzinfo=IST)
        market = {"spot": bars[k - 1]["c"], "spotBars1m": bars[:k], "futBars1m": [], "daily": prior,
                  "chains": [], "vix": None}
        a = analyze(cfg, market, now)
        if a["session"]["blocked"]:
            continue
        bias_state = day_type.apply_bias(a.get("dayType") or {}, bias_state, m)
        a["dayBias"] = bias_state.get("bias")
        a["code"], a["spot"] = code, bars[k - 1]["c"]
        last_vix = vm.get(m - 1, last_vix)
        if last_vix and vix_prev:
            a["vix"] = {"changePct": round((last_vix - vix_prev) / vix_prev * 100, 2)}
        raw = su.detect(a, cfg)
        ok, rejected = su.confirm_timeframes(a, raw)
        fo = fii_open.signal(code, a["spot"], now, change=fii) if fii else None
        if fo:
            ok = [fo, *ok]
        if k <= busy:
            continue  # a trade is open on this index: the live loop would not offer another
        for rj in rejected:
            s = next((x for x in raw if x["name"] == rj["name"] and x["side"] == rj["side"]), None)
            if s:
                cf(s, k, a.get("atr5") or 0.0, _rule_of(rj["reason"]), m)
        if not ok:
            continue
        for r in rows:
            r.outcome = r._final if r._until <= now else "PENDING"
        kept, why = guardrails.apply(rows, [{"side": s["side"], "setup": s["name"], "s": s} for s in ok], now)
        if not kept:
            for s in ok:
                cf(s, k, a.get("atr5") or 0.0, "GUARDRAIL: " + _rule_of(why or "limit"), m)
            continue
        for pk in sorted(kept, key=lambda p: -p["s"].get("strength", 0)):
            s = pk["s"]
            mode = mb.strike_mode({"dayType": a.get("dayType"), "dte": dte_cur}, s, now)
            exit_by = fii_open.exit_at(s["name"], as_of)
            r = premium_sim.simulate_momo(cfg, bars, k, s["side"], s["stop"], a.get("atr5") or 0.0, dte_next, bm,
                                          fixed_stop=bool(s.get("fixedStop")), close_min=close_m,
                                          exit_by_min=exit_by.hour * 60 + exit_by.minute if exit_by else None)
            if r is None:
                continue
            busy = r.exitIdx
            until = datetime(as_of.year, as_of.month, as_of.day, r.exitMinute // 60, r.exitMinute % 60, tzinfo=IST)
            row = guardrails_row(s["side"], now, until, "STOP_HIT" if r.outcome == "STOP" else "EXPIRED", s["name"])
            rows.append(row)
            trades.append({"date": day, "code": code, "time": f"{m // 60:02d}:{m % 60:02d}",
                           "exitTime": f"{r.exitMinute // 60:02d}:{r.exitMinute % 60:02d}", "setup": s["name"],
                           "side": s["side"], "mode": mode, "strike": r.strike, "delta": r.delta,
                           "entryPremium": r.entryPremium, "exitPremium": r.exitPremium, "pctMove": r.pctMove,
                           "outcome": r.outcome, "holdMinutes": r.holdMinutes, "riskPerLot": r.riskPerLot,
                           "premiumPerLot": r.premiumPerLot, "lotSize": cfg.lotSize, "netPnl": r.netPnl,
                           "reason": s.get("reason", "")})
            break
    return {"trades": trades, "blocked": blocked}


class guardrails_row:  # noqa: N801 -- what guardrails.apply() reads off a saved opportunity row
    def __init__(self, side: str, created: datetime, until: datetime, final: str, strategy: str) -> None:
        self.optionType, self.createdAt, self.outcome, self.resolvedAt = side, created, "PENDING", until
        self.strategy = strategy
        self._final, self._until = final, until


# ───────────────────────── portfolio (session rules) ─────────────────────────
def _portfolio(trades: list[dict[str, Any]], capital: float, max_loss_pct: float,
               sizing: str = "MAX_LOTS") -> dict[str, Any]:
    """Session view of the trade list. sizing MAX_LOTS: every trade buys as many lots as the CURRENT equity
    (capital + realised P&L) pays for; RISK: the live sizer (1 lot, refused when it risks more than the one-lot
    limit). Both: one index position at a time (correlated book), day stops once the loss reaches max_loss_pct."""
    max_lots_mode = sizing == "MAX_LOTS"
    taken, skipped = [], defaultdict(int)
    daily = []
    equity = capital
    for d in sorted({t["date"] for t in trades}):
        day_cap = equity * max_loss_pct / 100
        free_at, pnl, n = "00:00", 0.0, 0
        for t in sorted((x for x in trades if x["date"] == d), key=lambda x: x["time"]):
            if pnl <= -day_cap:
                skipped["daily max loss hit"] += 1
                continue
            if t["time"] < free_at:
                skipped["another index position already open"] += 1
                continue
            cash = equity + pnl
            lots = int(cash // t["premiumPerLot"]) if t["premiumPerLot"] > 0 else 0
            if lots < 1:
                skipped["premium above available capital"] += 1
                continue
            if not max_lots_mode:
                if t["riskPerLot"] > capital * one_lot_risk_pct() / 100:
                    skipped[f"1 lot risks more than {one_lot_risk_pct():g}% of capital"] += 1
                    continue
                lots = 1
            row = {**t, "lots": lots, "qty": lots * t["lotSize"], "capitalUsed": round(lots * t["premiumPerLot"], 2),
                   "riskAmount": round(lots * t["riskPerLot"], 2), "netPnlLots": round(lots * t["netPnl"], 2)}
            taken.append(row)
            pnl += row["netPnlLots"]
            n += 1
            free_at = t["exitTime"]
        equity += pnl
        daily.append({"date": d, "trades": n, "netPnl": round(pnl, 2), "cumPnl": round(equity - capital, 2),
                      "equity": round(equity, 2)})
    pnls = [t["netPnlLots"] for t in taken]
    eq_pnls = [x["netPnl"] for x in daily]
    return {"capital": capital, "sizing": sizing, "oneLotRiskPct": one_lot_risk_pct(), "maxLossPct": max_loss_pct,
            **_stats(pnls), "maxDrawdown": _drawdown(eq_pnls), "endingEquity": round(equity, 2),
            "returnPct": round((equity - capital) / capital * 100, 2) if capital else None,
            "avgLots": round(sum(t["lots"] for t in taken) / len(taken), 1) if taken else None,
            "maxLots": max((t["lots"] for t in taken), default=None),
            "skipped": dict(skipped), "daily": daily, "tradeList": taken}


# ───────────────────────── run ─────────────────────────
async def _run(job: dict[str, Any], d0: date, d1: date, codes: list[str], capital: float, max_loss_pct: float,
               sizing: str) -> None:
    def progress(msg: str, pct: float) -> None:
        job.update(stage=msg, progressPct=round(pct, 1))

    try:
        data = await _fetch(codes, d0, d1, progress)
        vix_daily = {b["t"][:10]: b["c"] for b in data["vixDaily"]}
        days = sorted({d for c in codes for d, v in data["spot"][c].items() if len(v) >= 60})
        if not days:
            raise ValueError("Upstox returned no 1-minute candles for this range (holidays only, too old, or token)")
        trades, blocked, errors = [], [], []
        total = len(days) * len(codes)
        done = 0
        for code in codes:
            for d in days:
                bars = data["spot"][code].get(d) or []
                done += 1
                progress(f"replaying {code} {d}", 25 + 73 * done / total)
                if len(bars) < 60:
                    continue
                prev_vix = next((vix_daily[x] for x in sorted(vix_daily, reverse=True) if x < d), None)
                res = await asyncio.to_thread(_replay_day, code, d, bars, data["daily"][code], prev_vix,
                                              data["vix1m"].get(d) or [])
                if "error" in res:
                    errors.append({"date": d, "code": code, "error": res["error"]})
                    continue
                trades += res["trades"]
                blocked += [{"date": d, "code": code, **b} for b in res["blocked"]]
        trades.sort(key=lambda t: (t["date"], t["time"]))
        job["result"] = _report(trades, blocked, days, codes, capital, max_loss_pct, errors, sizing)
        job.update(state="DONE", stage="done", progressPct=100.0, finishedAt=datetime.now(IST).isoformat())
    except Exception as e:  # noqa: BLE001
        logger.error(f"[RANGE_BACKTEST] {type(e).__name__}: {e}")
        job.update(state="FAILED", stage="failed", error=f"{type(e).__name__}: {e}",
                   finishedAt=datetime.now(IST).isoformat())


def _report(trades, blocked, days, codes, capital, max_loss_pct, errors, sizing="MAX_LOTS") -> dict[str, Any]:
    pnls = [t["netPnl"] for t in trades]
    mid = days[len(days) // 2] if days else ""
    by = lambda key, rows: {k: [r for r in rows if r[key] == k] for k in sorted({r[key] for r in rows})}  # noqa: E731
    per_index = [{"code": c, **_stats([t["netPnl"] for t in ts])} for c, ts in by("code", trades).items()]
    per_setup = sorted(({"setup": s, "policy": su.SETUP_POLICY.get(s, "DROPPED"), **_stats([t["netPnl"] for t in ts])}
                        for s, ts in by("setup", trades).items()), key=lambda x: x["netPnl"])
    rules = []
    for rule, rs in by("rule", blocked).items():
        st = _stats([b["netPnl"] for b in rs])
        verdict = "SAVED" if st["netPnl"] < 0 else "COST"
        rules.append({"rule": rule, "blockedSignals": len(rs), **st, "verdict": verdict,
                      "impact": round(-st["netPnl"], 2)})  # + = the rule saved money, - = it cost money
    rules.sort(key=lambda x: x["impact"])
    off = sorted(({"setup": s, "policy": su.SETUP_POLICY.get(s, "DROPPED"), **_stats([b["netPnl"] for b in bs])}
                  for s, bs in by("setup", blocked).items()), key=lambda x: x["netPnl"])
    daily = []
    cum = 0.0
    for d in days:
        p = sum(t["netPnl"] for t in trades if t["date"] == d)
        cum += p
        daily.append({"date": d, "trades": sum(1 for t in trades if t["date"] == d), "netPnl": round(p, 2),
                      "cumPnl": round(cum, 2)})
    return {
        "range": {"from": days[0] if days else None, "to": days[-1] if days else None, "tradingDays": len(days),
                  "codes": codes, "filters": settings.INSTITUTIONAL_FILTERS, "fiiOpenCodes": settings.FII_OPEN_CODES,
                  "pricing": "Black-Scholes at fixed IV off real Upstox index candles (estimate)"},
        "totals": {**_stats(pnls), "maxDrawdown": _drawdown(pnls),
                   "firstHalfPnl": round(sum(t["netPnl"] for t in trades if t["date"] < mid), 2),
                   "secondHalfPnl": round(sum(t["netPnl"] for t in trades if t["date"] >= mid), 2),
                   "tradesPerDay": round(len(trades) / len(days), 2) if days else 0, "splitNote": SPLIT_NOTE},
        "perIndex": per_index, "perSetup": per_setup, "ruleImpact": rules, "blockedSetups": off,
        "daily": daily, "portfolio": _portfolio(trades, capital, max_loss_pct, sizing), "trades": trades, "errors": errors,
    }


def start(from_date: str, to_date: str, codes: list[str], capital: float, max_loss_pct: float,
          sizing: str = "MAX_LOTS") -> dict[str, Any]:
    try:
        d0, d1 = date.fromisoformat(from_date), date.fromisoformat(to_date)
    except ValueError as e:
        raise BadRequestException("Dates must be YYYY-MM-DD") from e
    if d1 < d0:
        raise BadRequestException("toDate is before fromDate")
    if (d1 - d0).days > MAX_RANGE_DAYS:
        raise BadRequestException(f"Range is limited to {MAX_RANGE_DAYS} days per run")
    if d1 > datetime.now(IST).date():
        raise BadRequestException("toDate is in the future")
    bad = [c for c in codes if not get_config(c) or get_config(c).type != "INDEX"]
    if bad:
        raise BadRequestException(f"Not an index underlying: {', '.join(bad)}")
    if any(j["state"] == "RUNNING" for j in _jobs.values()):
        raise ConflictException("A backtest is already running; wait for it to finish")
    jid = uuid.uuid4().hex[:12]
    job = {"jobId": jid, "state": "RUNNING", "stage": "starting", "progressPct": 0.0,
           "startedAt": datetime.now(IST).isoformat(), "finishedAt": None, "error": None, "result": None,
           "request": {"fromDate": from_date, "toDate": to_date, "codes": codes, "capital": capital,
                       "maxLossPct": max_loss_pct, "sizing": sizing}}
    _jobs[jid] = job
    for k in [k for k in _jobs if k != jid][:-5]:  # keep the last few results only
        _jobs.pop(k, None)
    asyncio.get_running_loop().create_task(_run(job, d0, d1, codes, capital, max_loss_pct, sizing))
    return {k: v for k, v in job.items() if k != "result"}


def status(job_id: str) -> dict[str, Any] | None:
    return _jobs.get(job_id)
