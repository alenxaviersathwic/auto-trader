"""
Daily-bar indicator math for the strategy backtester. The live/intraday engine already has
EMA/ATR/ADX/VWAP in opportunities/service/market_analysis.py (reused here as-is: they operate on
plain OHLCV bar dicts and are not actually intraday-specific); this file adds the remaining
indicator codes the strategy rule-tree registry knows about (SMA, RSI, CCI, SUPERTREND) so a
backtest can feed the exact same RuleEvaluator the exact same `indicators.<CODE>` shape the live
engine builds from intraday snapshots -- just computed from daily bars instead.
"""
from typing import Any

Bar = dict[str, Any]  # {"t","o","h","l","c","v"}


def sma(values: list[float], n: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < n:
            out.append(None)
        else:
            out.append(sum(values[i + 1 - n : i + 1]) / n)
    return out


def rsi(closes: list[float], n: int = 14) -> list[float | None]:
    """Wilder's RSI."""
    out: list[float | None] = [None] * len(closes)
    if len(closes) < n + 1:
        return out
    gains = [max(closes[i] - closes[i - 1], 0.0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0.0) for i in range(1, len(closes))]
    avg_gain = sum(gains[:n]) / n
    avg_loss = sum(losses[:n]) / n
    out[n] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    for i in range(n, len(gains)):
        avg_gain = (avg_gain * (n - 1) + gains[i]) / n
        avg_loss = (avg_loss * (n - 1) + losses[i]) / n
        out[i + 1] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def cci(bars: list[Bar], n: int = 20) -> list[float | None]:
    tp = [(b["h"] + b["l"] + b["c"]) / 3 for b in bars]
    out: list[float | None] = []
    for i in range(len(tp)):
        if i + 1 < n:
            out.append(None)
            continue
        window = tp[i + 1 - n : i + 1]
        mean = sum(window) / n
        mad = sum(abs(x - mean) for x in window) / n
        out.append(None if mad == 0 else (tp[i] - mean) / (0.015 * mad))
    return out


def supertrend(bars: list[Bar], n: int = 10, mult: float = 3.0) -> list[dict[str, Any] | None]:
    """Returns, per bar, {"value": <line>, "trend": "UP"|"DOWN"} once enough bars exist, else None."""
    from app.modules.opportunities.service.market_analysis import atr as _atr_window

    out: list[dict[str, Any] | None] = [None] * len(bars)
    if len(bars) < n + 1:
        return out
    trend = "UP"
    final_upper = final_lower = None
    for i in range(n, len(bars)):
        window = bars[: i + 1]
        a = _atr_window(window, n)
        hl2 = (bars[i]["h"] + bars[i]["l"]) / 2
        basic_upper, basic_lower = hl2 + mult * a, hl2 - mult * a
        prev_close = bars[i - 1]["c"]
        if final_upper is None:
            final_upper, final_lower = basic_upper, basic_lower
        else:
            final_upper = basic_upper if (basic_upper < final_upper or prev_close > final_upper) else final_upper
            final_lower = basic_lower if (basic_lower > final_lower or prev_close < final_lower) else final_lower
        close = bars[i]["c"]
        if trend == "UP" and close < final_lower:
            trend = "DOWN"
        elif trend == "DOWN" and close > final_upper:
            trend = "UP"
        out[i] = {"value": final_lower if trend == "UP" else final_upper, "trend": trend}
    return out
