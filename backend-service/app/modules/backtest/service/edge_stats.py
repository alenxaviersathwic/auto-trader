"""
Edge statistics for a strategy's trade list -- is there an edge, or just noise? Pure functions, no I/O.

11 Nov 2026 research review (gap 3): decisions were being made on 8-19 trades. ~12 setups x 6 underlyings x strike
modes x timeframes is hundreds of implicit trials, so the best-looking setup is expected to look good by luck.

  summarize(pnls)                  n, win rate, expectancy, its 95% CI, t-stat, profit factor, max drawdown
  probabilistic_sharpe(pnls, sr0)  P(true per-trade Sharpe > sr0)                     (Bailey & Lopez de Prado 2012)
  expected_max_sharpe(n_trials, v) the best Sharpe expected from n_trials of NO-edge strategies
  deflated_sharpe(pnls, n_trials)  PSR against that hurdle -- the bar rises with every setup / parameter tried
                                   (Bailey & Lopez de Prado, J. Portfolio Mgmt 2014)
  kill_verdict(pnls, ...)          SUSPEND when the last KILL_WINDOW trades' expectancy is below zero at 90%
                                   one-sided confidence, or the drawdown exceeds 2x the backtest max
  promotion_verdict(pnls, n_trials) LIVE only with >= MIN_OOS_TRADES out-of-sample trades and DSR > MIN_DSR

`pnls` are per-trade NET results (rupees or R-multiples -- the statistics are scale-free except the drawdown).
"""
import math
from statistics import NormalDist
from typing import Any

_N = NormalDist()
EULER_GAMMA = 0.5772156649015329
KILL_WINDOW = 50
KILL_CONFIDENCE = 0.90
MIN_OOS_TRADES = 200
MIN_DSR = 0.95
DRAWDOWN_KILL_MULT = 2.0


def _mean(x: list[float]) -> float:
    return sum(x) / len(x)


def _std(x: list[float]) -> float:
    if len(x) < 2:
        return 0.0
    m = _mean(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def _moments(x: list[float]) -> tuple[float, float]:
    """(skew, kurtosis) -- kurtosis NOT excess (normal = 3)."""
    n = len(x)
    m = _mean(x)
    s2 = sum((v - m) ** 2 for v in x) / n
    if n < 3 or s2 <= 0:
        return 0.0, 3.0
    s = math.sqrt(s2)
    skew = sum((v - m) ** 3 for v in x) / n / s ** 3
    kurt = sum((v - m) ** 4 for v in x) / n / s ** 4
    return skew, kurt


def max_drawdown(pnls: list[float]) -> float:
    peak = eq = dd = 0.0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return dd


def summarize(pnls: list[float]) -> dict[str, Any]:
    n = len(pnls)
    if n == 0:
        return {"n": 0}
    m, sd = _mean(pnls), _std(pnls)
    se = sd / math.sqrt(n) if n > 1 else float("inf")
    t = 1.959963984540054
    wins, losses = [p for p in pnls if p > 0], [p for p in pnls if p <= 0]
    gl = -sum(losses)
    return {
        "n": n, "winRate": round(len(wins) / n * 100, 1), "expectancy": round(m, 2),
        "ci95": (round(m - t * se, 2), round(m + t * se, 2)) if n > 1 else (None, None),
        "tStat": round(m / se, 2) if n > 1 and se > 0 else None,
        "profitFactor": round(sum(wins) / gl, 2) if gl > 0 else None,
        "avgWin": round(_mean(wins), 2) if wins else 0.0, "avgLoss": round(_mean(losses), 2) if losses else 0.0,
        "net": round(sum(pnls), 2), "maxDrawdown": round(max_drawdown(pnls), 2),
        "sharpePerTrade": round(m / sd, 3) if sd > 0 else None,
    }


def probabilistic_sharpe(pnls: list[float], sr0: float = 0.0) -> float | None:
    """P(true Sharpe > sr0) given the sample's length, skew and kurtosis (per-trade, not annualised)."""
    n = len(pnls)
    sd = _std(pnls)
    if n < 3 or sd <= 0:
        return None
    sr = _mean(pnls) / sd
    skew, kurt = _moments(pnls)
    denom = 1 - skew * sr + (kurt - 1) / 4 * sr * sr
    if denom <= 0:
        return None
    return _N.cdf((sr - sr0) * math.sqrt(n - 1) / math.sqrt(denom))


def expected_max_sharpe(n_trials: int, sharpe_variance: float) -> float:
    """E[max Sharpe] of n_trials independent zero-edge strategies whose Sharpe estimates have this variance."""
    if n_trials <= 1 or sharpe_variance <= 0:
        return 0.0
    sd = math.sqrt(sharpe_variance)
    return sd * ((1 - EULER_GAMMA) * _N.inv_cdf(1 - 1 / n_trials)
                 + EULER_GAMMA * _N.inv_cdf(1 - 1 / (n_trials * math.e)))


def deflated_sharpe(pnls: list[float], n_trials: int, sharpe_variance: float | None = None) -> float | None:
    """PSR against the expected best-of-n_trials Sharpe. `sharpe_variance` = variance of the Sharpe ratios across
    the trials you actually ran; when unknown, the sampling variance of a zero-edge Sharpe, 1/(n-1), is used."""
    n = len(pnls)
    if n < 3:
        return None
    v = sharpe_variance if sharpe_variance is not None else 1.0 / (n - 1)
    return probabilistic_sharpe(pnls, expected_max_sharpe(max(1, n_trials), v))


def kill_verdict(pnls: list[float], backtest_max_dd: float | None = None, window: int = KILL_WINDOW,
                 confidence: float = KILL_CONFIDENCE) -> tuple[bool, str]:
    """(suspend?, why). Uses the last `window` trades; needs at least half a window before it can convict."""
    recent = pnls[-window:]
    n = len(recent)
    if backtest_max_dd and max_drawdown(pnls) > DRAWDOWN_KILL_MULT * backtest_max_dd:
        return True, f"drawdown {max_drawdown(pnls):,.0f} > {DRAWDOWN_KILL_MULT:g}x backtest max {backtest_max_dd:,.0f}"
    if n < window // 2:
        return False, f"only {n} trades: not enough to convict (need {window // 2})"
    m, sd = _mean(recent), _std(recent)
    if sd <= 0:
        return (m < 0), f"expectancy {m:+.2f} with no variance"
    upper = m + _N.inv_cdf(confidence) * sd / math.sqrt(n)
    if upper < 0:
        return True, f"last {n} trades: expectancy {m:+.2f}, {confidence:.0%} upper bound {upper:+.2f} < 0"
    return False, f"last {n} trades: expectancy {m:+.2f}, upper bound {upper:+.2f}"


def promotion_verdict(pnls: list[float], n_trials: int) -> tuple[bool, str]:
    """(may trade real money?, why). Out-of-sample trades only."""
    n = len(pnls)
    if n < MIN_OOS_TRADES:
        return False, f"{n} out-of-sample trades < {MIN_OOS_TRADES}"
    dsr = deflated_sharpe(pnls, n_trials)
    if dsr is None or dsr <= MIN_DSR:
        return False, f"deflated Sharpe {dsr if dsr is None else round(dsr, 3)} <= {MIN_DSR} after {n_trials} trials"
    return True, f"{n} OOS trades, deflated Sharpe {dsr:.3f} after {n_trials} trials"
