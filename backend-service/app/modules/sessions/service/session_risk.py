"""
Session risk level (LOW / MEDIUM / HIGH): how strict a session is about WHICH opportunities it accepts.
Pure rules, no I/O.

It changes entry strictness only. Position size (session_sizing.RISK_PER_TRADE_PCT, the one-lot allowance), the
session loss limit (maxLossPercentage) and the parallel-trade cap are the same at every level, so a small account
can always take one lot.

  LOW     proven setups only: setups.SETUP_POLICY CORE (the backtested momentum engine) and CONFIRMED (the Fib
          golden pocket with its OI + volume confirmations); with the trend; reward:risk >= 1.5
  MEDIUM  any coded setup the policy lets trade (CORE / MERGED / CONFIRMED); with the trend; reward:risk >= 1.3
  HIGH    everything the engine saves, including AI picks without a coded setup and picks against the trend
          (this is how every session behaved before 16 Nov 2026)

The model's `confidence` is deliberately NOT used: it is not calibrated (session_sizing.py module docstring), and on
the 3-5 Nov 2026 opportunities the confidence-based LOW / MEDIUM / HIGH label on each opportunity did not separate
winners from losers. The gate uses the things that have evidence behind them: the setup policy and the trend side.
"""
from dataclasses import dataclass
from typing import Any

RISK_LEVELS: tuple[str, ...] = ("LOW", "MEDIUM", "HIGH")
DEFAULT_RISK_LEVEL = "LOW"
LEGACY_RISK_LEVEL = "HIGH"  # sessions created before the column existed accepted everything


@dataclass(frozen=True)
class RiskProfile:
    level: str
    policies: frozenset[str] | None  # allowed SETUP_POLICY classes; None = any strategy, coded or not
    minRewardRisk: float
    allowAgainstTrend: bool
    summary: str

    def as_dict(self) -> dict[str, Any]:
        return {"level": self.level, "setups": sorted(self.policies) if self.policies else ["ANY"],
                "minRewardRisk": self.minRewardRisk, "allowAgainstTrend": self.allowAgainstTrend,
                "summary": self.summary}


RISK_PROFILES: dict[str, RiskProfile] = {
    "LOW": RiskProfile("LOW", frozenset({"CORE", "CONFIRMED"}), 1.5, False,
                       "Proven setups only, with the trend, reward:risk 1.5 or better"),
    "MEDIUM": RiskProfile("MEDIUM", frozenset({"CORE", "MERGED", "CONFIRMED"}), 1.3, False,
                          "Any coded setup, with the trend, reward:risk 1.3 or better"),
    "HIGH": RiskProfile("HIGH", None, 0.0, True, "Everything the engine finds, including against-trend picks"),
}


def normalize_risk_level(level: str | None) -> str:
    lv = (level or "").strip().upper()
    return lv if lv in RISK_PROFILES else DEFAULT_RISK_LEVEL


def profile_for(level: str | None) -> RiskProfile:
    return RISK_PROFILES[normalize_risk_level(level)]


def is_against_trend(risks: list[Any] | None) -> bool:
    """The engine marks a counter-trend pick with a first risk line 'Against the <bias> trend' (graph/nodes.py)."""
    return any(str(r).strip().lower().startswith("against the") for r in (risks or []))


def risk_gate(level: str | None, strategy: str | None, reward_risk: float, risks: list[Any] | None) -> str | None:
    """Why this opportunity is too risky for a session at `level`, or None when the session may take it."""
    prof = profile_for(level)
    if prof.policies is not None:
        from app.modules.opportunities.service.setups import SETUP_POLICY  # lazy: heavy import

        pol = SETUP_POLICY.get((strategy or "").strip())
        if pol not in prof.policies:
            what = "not a proven setup" if prof.level == "LOW" else "not a coded setup"
            return f"{prof.level} risk: {what}"
    if not prof.allowAgainstTrend and is_against_trend(risks):
        return f"{prof.level} risk: against the trend"
    if float(reward_risk or 0.0) < prof.minRewardRisk:
        return f"{prof.level} risk: reward:risk below {prof.minRewardRisk:g}"
    return None
