"""
Per-strategy backtest: replays a RULE_TREE strategy's own entry/exit conditions against daily
bars of its underlying, using the exact same RuleEvaluator the live "Interactive Rule Tree
Evaluation Testbed" (StrategyTestPanel) uses -- just fed indicator values computed from daily
bars instead of a hand-typed intraday snapshot.

Honesty about what this is and isn't:
- It measures the UNDERLYING's move, not option premium P&L -- 20 years of Indian option-chain
  history doesn't exist anywhere this platform can reach, so there is no way to backtest actual
  premium decay/skew that far back. A win here means "the underlying moved favourably", not
  "the option would have hit +N%".
- Any indicator the strategy's rule tree references with an intraday timeframe (RSI on 5m, say)
  is computed here on DAILY bars instead -- same formula, different bar size. That changes what
  the number means, so results are a directional sanity check on the underlying edge, not a
  faithful replay of the live intraday strategy.
- Exit uses the strategy's own `exit.when` rule if it fires, else a 1.5xATR(14) stop / 2R target
  on the underlying, else a 10-trading-day time-stop -- whichever comes first. This project's own
  playbook (docs/04-risk-and-profit-management.md) already defines expectancy the same way this
  reports it: win% x avg_win - loss% x avg_loss - costs (costs omitted here: no premium, no fees).
- INDEX underlyings only. MCX futures roll monthly and Upstox has no historical series for an
  expired contract, so there's no single instrument key to pull years of MCX history from.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.db.session import async_session_factory
from app.modules.opportunities.provider.underlying_config import get_config
from app.modules.opportunities.provider.upstox_market_data import MarketDataUnavailable, market_data
from app.modules.opportunities.service.market_analysis import adx as _adx, atr as _atr, ema as _ema, vwap as _vwap
from app.modules.strategies.repository.strategy_repository import StrategyRepository
from app.modules.strategies.schema.performance_schema import PerformanceSnapshotCreate
from app.modules.strategies.schema.strategy_schema import StrategyFilter
from app.modules.strategies.service.backtest_indicators import cci as _cci, rsi as _rsi, sma as _sma, supertrend as _supertrend
from app.modules.strategies.service.rule_evaluator import RuleEvaluator

DEFAULT_ASSUMED_CAPITAL = Decimal("100000")  # used only to translate a %-return backtest into an
                                              # illustrative rupee figure when the strategy has no
                                              # riskProfile.marginAmount of its own -- see run_all()'s
                                              # docstring for why this is notional, not real P&L.

HOLD_DAYS_MAX = 10
STOP_ATR_MULT = 1.5
REWARD_RISK = 2.0


class BacktestUnsupported(Exception):
    pass


@dataclass
class Trade:
    entryDate: str
    exitDate: str
    side: str
    entryPrice: float
    exitPrice: float
    pnlPct: float
    outcome: str  # TARGET | STOP | RULE_EXIT | TIME_STOP


@dataclass
class BacktestResult:
    underlyingCode: str
    fromDate: str
    toDate: str
    barsUsed: int
    trades: list[Trade] = field(default_factory=list)
    totalTrades: int = 0
    winRatePct: float = 0.0
    avgWinPct: float = 0.0
    avgLossPct: float = 0.0
    profitFactor: float | None = None
    expectancyPct: float = 0.0
    totalReturnPct: float = 0.0
    maxDrawdownPct: float = 0.0
    note: str = ""


def _collect_indicator_specs(node: Any, out: set[tuple[str, int, float]]) -> None:
    """Recursively walk the rule-tree JSON for every {"source": "INDICATOR", ...} operand."""
    if isinstance(node, dict):
        if node.get("source") == "INDICATOR" and node.get("code"):
            p = node.get("params") or {}
            out.add((node["code"], int(p.get("period", 14)), float(p.get("multiplier", 3.0))))
        for v in node.values():
            _collect_indicator_specs(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_indicator_specs(v, out)


def _series_for(code: str, period: int, mult: float, bars: list[dict[str, Any]]) -> list[Any]:
    closes = [b["c"] for b in bars]
    if code in ("EMA",):
        return _ema(closes, period)
    if code == "SMA":
        return _sma(closes, period)
    if code == "RSI":
        return _rsi(closes, period)
    if code == "CCI":
        return _cci(bars, period)
    if code == "ATR":
        return [None if i < 1 else _atr(bars[: i + 1], period) for i in range(len(bars))]
    if code == "ADX":
        return [None if i < 2 * period else _adx(bars[: i + 1], period) for i in range(len(bars))]
    if code == "VWAP":
        w = max(period, 1)
        return [None if i < 1 else _vwap(bars[max(0, i - w + 1) : i + 1]) for i in range(len(bars))]
    if code == "SUPERTREND":
        return _supertrend(bars, period, mult)
    return [None] * len(bars)


def _context_at(bars: list[dict[str, Any]], i: int, series: dict[tuple[str, int, float], list[Any]]) -> dict[str, Any]:
    cur, prev = bars[i], (bars[i - 1] if i > 0 else bars[i])
    cur_p = {"open": cur["o"], "high": cur["h"], "low": cur["l"], "close": cur["c"], "volume": cur.get("v", 0)}
    prev_p = {"open": prev["o"], "high": prev["h"], "low": prev["l"], "close": prev["c"], "volume": prev.get("v", 0)}
    indicators: dict[str, Any] = {}
    for (code, period, mult), s in series.items():
        val = s[i]
        if code == "SUPERTREND":
            indicators[code] = val or {"value": None, "trend": None}
        elif code == "ADX":
            indicators[code] = {"adx": val, "plusDi": None, "minusDi": None, "value": val}
        elif code == "VWAP":
            indicators[code] = {"currentDay": val, "upperBand": None, "lowerBand": None, "value": val}
        else:
            indicators[code] = {"value": val}
    return {
        "prices": {"current": cur_p, "previous": prev_p},
        "days": {"TODAY": cur_p, "YESTERDAY": prev_p},
        "indicators": indicators,
        "parameters": {},
    }


def simulate(definition: dict[str, Any], bars: list[dict[str, Any]]) -> BacktestResult:
    evaluator = RuleEvaluator()
    specs: set[tuple[str, int, float]] = set()
    _collect_indicator_specs(definition, specs)
    series = {s: _series_for(s[0], s[1], s[2], bars) for s in specs}
    max_period = max([s[1] * 2 for s in specs] + [15])

    trades: list[Trade] = []
    position: dict[str, Any] | None = None
    equity = 0.0
    equity_curve = [0.0]
    peak = 0.0
    max_dd = 0.0

    for i in range(max_period, len(bars) - 1):
        ctx = _context_at(bars, i, series)
        if position is None:
            res = evaluator.evaluate_strategy(definition, ctx)
            if res.entryMet:
                case = next((c for c in definition.get("cases", []) if str(c.get("key")) == res.activeCaseKey), {})
                side = "UP" if (case.get("bias") or "BULLISH").upper() == "BULLISH" else "DOWN"
                entry_price = bars[i + 1]["o"]  # enter at next day's open
                a = _atr(bars[: i + 1], 14) or (bars[i]["h"] - bars[i]["l"]) or entry_price * 0.01
                stop = entry_price - STOP_ATR_MULT * a if side == "UP" else entry_price + STOP_ATR_MULT * a
                target = entry_price + REWARD_RISK * STOP_ATR_MULT * a if side == "UP" else entry_price - REWARD_RISK * STOP_ATR_MULT * a
                position = {"entryIdx": i + 1, "entryDate": bars[i + 1]["t"][:10], "side": side,
                            "entryPrice": entry_price, "stop": stop, "target": target}
            continue

        j = position["entryIdx"]
        if i < j:
            continue
        bar = bars[i]
        side = position["side"]
        outcome = None
        exit_price = bar["c"]
        if side == "UP":
            if bar["l"] <= position["stop"]:
                outcome, exit_price = "STOP", position["stop"]
            elif bar["h"] >= position["target"]:
                outcome, exit_price = "TARGET", position["target"]
        else:
            if bar["h"] >= position["stop"]:
                outcome, exit_price = "STOP", position["stop"]
            elif bar["l"] <= position["target"]:
                outcome, exit_price = "TARGET", position["target"]
        if not outcome:
            ctx_now = _context_at(bars, i, series)
            res = evaluator.evaluate_strategy(definition, ctx_now)
            if res.exitMet:
                outcome = "RULE_EXIT"
            elif i - j >= HOLD_DAYS_MAX:
                outcome = "TIME_STOP"
        if outcome:
            pnl_pct = ((exit_price - position["entryPrice"]) / position["entryPrice"] * 100
                       if side == "UP" else (position["entryPrice"] - exit_price) / position["entryPrice"] * 100)
            trades.append(Trade(position["entryDate"], bar["t"][:10], side, round(position["entryPrice"], 2),
                                 round(exit_price, 2), round(pnl_pct, 2), outcome))
            equity += pnl_pct
            equity_curve.append(equity)
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)
            position = None

    wins = [t.pnlPct for t in trades if t.pnlPct > 0]
    losses = [t.pnlPct for t in trades if t.pnlPct <= 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else None
    expectancy = (win_rate / 100) * avg_win + (1 - win_rate / 100) * avg_loss

    return BacktestResult(
        underlyingCode="", fromDate=bars[0]["t"][:10] if bars else "", toDate=bars[-1]["t"][:10] if bars else "",
        barsUsed=len(bars), trades=trades, totalTrades=len(trades), winRatePct=round(win_rate, 1),
        avgWinPct=round(avg_win, 2), avgLossPct=round(avg_loss, 2),
        profitFactor=round(profit_factor, 2) if profit_factor is not None else None,
        expectancyPct=round(expectancy, 2), totalReturnPct=round(equity, 1), maxDrawdownPct=round(max_dd, 1),
    )


class BacktestService:
    def __init__(self, strategy_repo: StrategyRepository | None = None):
        self.strategy_repo = strategy_repo or StrategyRepository()

    async def run(self, strategy_id: int, underlying_code: str | None = None, years: int = 20) -> BacktestResult:
        async with async_session_factory() as session:
            strat = await self.strategy_repo.get_by_id(session, strategy_id)
            if not strat:
                raise BacktestUnsupported(f"Strategy {strategy_id} not found")
            version = next((v for v in strat.versions if v.id == strat.currentVersionId), None) or (
                strat.versions[0] if strat.versions else None
            )
            if not version or not version.definition:
                raise BacktestUnsupported("This strategy has no saved rule-tree definition to backtest")
            if not strat.executable:
                raise BacktestUnsupported(
                    f"'{strat.name}' has no executable entry/exit rules yet (it's a descriptive/legacy "
                    "definition -- indicators and labels only, no rule tree) -- there is nothing for a "
                    "backtest to replay. Build out the rule tree on the Definition tab first."
                )
            code = (underlying_code or next((m for m in (strat.markets or []) if get_config(m)), None) or "").upper()
            cfg = get_config(code) if code else None
            if not cfg:
                raise BacktestUnsupported(
                    f"No backtestable underlying found on this strategy's markets {strat.markets!r} "
                    "(backtest needs one of this platform's configured INDEX underlyings)"
                )
            if cfg.type != "INDEX":
                raise BacktestUnsupported(
                    f"{code} is a commodity: MCX futures roll monthly and Upstox keeps no historical "
                    "series for an expired contract, so there's no single key to pull years of history from"
                )
            try:
                bars = await market_data.historical_daily(cfg, session, years=years)
            except MarketDataUnavailable as e:
                raise BacktestUnsupported(f"Couldn't fetch historical daily bars for {code}: {e}") from e
            if len(bars) < 60:
                raise BacktestUnsupported(
                    f"Upstox returned only {len(bars)} daily bars for {code} -- not enough for a meaningful backtest"
                )
            result = simulate(version.definition, bars)
            result.underlyingCode = code
            if result.totalTrades > 0:
                from app.modules.strategies.service.strategy_service import compute_stop_loss_from_win_rate

                strat.stopLossPct = compute_stop_loss_from_win_rate(result.winRatePct)
                await self.strategy_repo.save(session, strat)
                await session.commit()
            years_covered = (date.fromisoformat(result.toDate) - date.fromisoformat(result.fromDate)).days / 365.25
            result.note = (
                f"{years_covered:.1f} years of daily bars actually available from Upstox for {code} "
                f"({result.fromDate} to {result.toDate}) -- short of the {years}-year request; Upstox's own "
                "retention for daily candles is the limit, not this platform."
            )
            return result

    async def run_all(self, years: int = 20) -> dict[str, Any]:
        """
        Backtests every strategy that can be (executable rule tree + an INDEX underlying on its
        markets) and records the result as a "BACKTEST"-source performance snapshot via the same
        add_performance_snapshot() the Performance tab's manual entry uses -- so it shows up there
        as its own source, alongside any real PAPER/LIVE history, never overwriting it. A strategy
        still marked UNTESTED is bumped to BACKTESTED once it has a result. Strategies that can't be
        backtested (no rule tree, MCX-only, Upstox has nothing for them, etc.) are skipped and
        reported, not treated as failures -- one bad strategy never stops the batch.

        netPnl and maxDrawdown are stored in this schema as rupee figures, but this engine only
        produces a % return on the underlying (see the module docstring on why there's no real
        premium P&L to compute here). So both are translated to rupees against an ASSUMED capital
        figure -- the strategy's own riskProfile.marginAmount if it has one, else
        DEFAULT_ASSUMED_CAPITAL -- making them illustrative, not a claim of real money made or lost.
        """
        from app.modules.strategies.service.strategy_service import StrategyService  # lazy: avoid import cycle

        strategy_service = StrategyService(strategy_repo=self.strategy_repo)

        strategies = []
        page = 0
        while True:
            async with async_session_factory() as session:
                page_res = await self.strategy_repo.search(session, StrategyFilter(page=page, limit=100))
            strategies.extend(page_res.list)
            page += 1
            if page >= page_res.totalPages or not page_res.list:
                break

        results: list[dict[str, Any]] = []
        for strat in strategies:
            try:
                result = await self.run(strat.id, None, years)
            except BacktestUnsupported as e:
                results.append({"id": strat.id, "code": strat.code, "status": "skipped", "reason": str(e)})
                continue
            except Exception as e:  # keep the batch going even if one strategy blows up unexpectedly
                results.append({"id": strat.id, "code": strat.code, "status": "error", "reason": str(e)})
                continue

            wins = sum(1 for t in result.trades if t.pnlPct > 0)
            losses = len(result.trades) - wins
            pf = (
                Decimal(str(result.profitFactor)) if result.profitFactor is not None
                else (Decimal("99.99") if wins > 0 else Decimal("0"))
            )

            async with async_session_factory() as session:
                strat_row = await self.strategy_repo.get_by_id(session, strat.id)
                if not strat_row:
                    results.append({"id": strat.id, "code": strat.code, "status": "error",
                                     "reason": "strategy disappeared mid-batch"})
                    continue

                assumed_capital = DEFAULT_ASSUMED_CAPITAL
                margin = (strat_row.riskProfile or {}).get("marginAmount")
                if margin:
                    try:
                        assumed_capital = Decimal(str(margin))
                    except InvalidOperation:
                        pass

                payload = PerformanceSnapshotCreate(
                    source="BACKTEST",
                    domain="UNKNOWN",
                    periodFrom=date.fromisoformat(result.fromDate) if result.fromDate else None,
                    periodTo=date.fromisoformat(result.toDate) if result.toDate else None,
                    totalTrades=result.totalTrades,
                    winningTrades=wins,
                    losingTrades=losses,
                    winRatePct=Decimal(str(result.winRatePct)),
                    netPnl=(assumed_capital * Decimal(str(result.totalReturnPct)) / Decimal("100")).quantize(Decimal("0.01")),
                    profitFactor=pf,
                    maxDrawdown=(assumed_capital * Decimal(str(result.maxDrawdownPct)) / Decimal("100")).quantize(Decimal("0.01")),
                )
                await strategy_service.add_performance_snapshot(session, strat.id, payload)
                if strat_row.validationStatus == "UNTESTED":
                    strat_row.validationStatus = "BACKTESTED"
                    await self.strategy_repo.save(session, strat_row)

            results.append({
                "id": strat.id, "code": strat.code, "status": "ok",
                "underlyingCode": result.underlyingCode, "totalTrades": result.totalTrades,
                "winRatePct": result.winRatePct, "totalReturnPct": result.totalReturnPct,
            })

        return {
            "total": len(strategies),
            "backtested": sum(1 for r in results if r["status"] == "ok"),
            "skipped": sum(1 for r in results if r["status"] == "skipped"),
            "errors": sum(1 for r in results if r["status"] == "error"),
            "results": results,
        }
