"""
Pure rules a MANUAL session loop applies to an already-created opportunity (no I/O, fully unit-testable).

  capital_state()   current capital, free cash, loss budget left -- from the session row + its LOCKED picks
  entry_ceiling()   highest entry price at which the trade still pays at least MIN_RR_AT_ENTRY
  usage_fraction()  how much of the affordable size to use, from the win probability
  size_candidate()  lots = 1 .. max affordable, scaled by win probability

There is NO trade-count limit. The caps are the money ones: free cash, the session loss budget
(maxLossPercentage of capital, G-RISK-DAY) and -- since the 11 Nov 2026 research review (gap 9) -- a FIXED-FRACTIONAL
per-trade risk: at most RISK_PER_TRADE_PCT of capital between entry and stop. Size no longer scales with the
model's "confidence": that number is not calibrated (the 75-84 bucket won 0% on 4 Nov), and Kelly-style sizing on an
unproven edge with n < 200 trades is guesswork. One lot is still allowed when it risks <= MAX_ONE_LOT_RISK_PCT.

correlated_block() treats NIFTY / BANKNIFTY / FINNIFTY / MIDCPNIFTY / SENSEX / BANKEX as ONE bet: they move together
intraday, so a CE on NIFTY and a CE on BANKNIFTY is the same long position twice.
"""
import math
from dataclasses import asdict, dataclass
from typing import Any

from app.modules.opportunities.service.costs import round_trip_cost_pct
from app.modules.opportunities.service.menu_builder import expected_edge_pct

MIN_PICK_WINDOW_SECONDS = 8       # an opportunity that expires within this many seconds cannot be acted on: never offered
MAX_OPPORTUNITY_AGE_SECONDS = 30  # only opportunities inserted in the last 30 s are read: older entries are stale
MAX_OPEN_OFFERS = 10              # rows shown at once in the session table (a display cap, not a trade limit)
MIN_WIN_PROB = 0.5                # at or below this win probability only the minimum size (1 lot) is used
MIN_RR_AT_ENTRY = 1.2             # same reward:risk floor the opportunity menu uses
TICK = 0.05                       # option price tick
RISK_PER_TRADE_PCT = 0.5          # fixed-fractional: rupees between entry and stop, as % of session capital
MAX_ONE_LOT_RISK_PCT = 1.0        # a single lot may risk up to this much when RISK_PER_TRADE_PCT buys < 1 lot
CORRELATED_INDEX_GROUP = frozenset({"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "BANKEX"})
MAX_SAME_DIRECTION_CORRELATED = 1  # open same-direction positions across the group (CE = long, PE = short)


@dataclass(frozen=True)
class CapitalState:
    capital: float
    realizedPnl: float
    currentCapital: float         # capital + realised P&L
    committedPremium: float       # premium locked into LOCKED picks
    availableCapital: float       # currentCapital - committedPremium (never below 0)
    maxLossAmount: float          # capital * maxLossPercentage / 100
    lossUsed: float               # realised loss so far (0 while in profit)
    committedRisk: float          # worst-case loss of LOCKED picks (stop hit on all of them)
    remainingLossBudget: float    # maxLossAmount - lossUsed - committedRisk (never below 0)
    lockedTrades: int             # picks locked so far (informational -- there is no limit)

    def as_dict(self) -> dict[str, Any]:
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def capital_state(capital: float, max_loss_pct: float, realized_pnl: float, locked: list[Any]) -> CapitalState:
    """`locked` = this session's LOCKED picks (objects with capitalRequired / riskAmount)."""
    capital, realized_pnl = float(capital), float(realized_pnl)
    current = capital + realized_pnl
    committed_premium = sum(float(p.capitalRequired) for p in locked)
    committed_risk = sum(float(p.riskAmount) for p in locked)
    max_loss = capital * float(max_loss_pct) / 100.0
    loss_used = max(0.0, -realized_pnl)
    return CapitalState(
        capital=capital, realizedPnl=realized_pnl, currentCapital=current,
        committedPremium=committed_premium, availableCapital=max(0.0, current - committed_premium),
        maxLossAmount=max_loss, lossUsed=loss_used, committedRisk=committed_risk,
        remainingLossBudget=max(0.0, max_loss - loss_used - committed_risk),
        lockedTrades=len(locked),
    )


def entry_ceiling(entry: float, stop: float, target: float, min_rr: float = MIN_RR_AT_ENTRY) -> float:
    """Highest price p with (target - p) / (p - stop) >= min_rr, floored to the tick; never below `entry`.
    Above it the stop and target stay fixed but the trade no longer pays enough, so the trader must not chase."""
    p = (target + min_rr * stop) / (1.0 + min_rr)
    return max(entry, math.floor(p / TICK + 1e-9) * TICK)


@dataclass(frozen=True)
class SizedCandidate:
    lots: int
    lotUnits: int
    quantity: int
    entryMax: float
    capitalRequired: float
    riskAmount: float
    rewardAmount: float
    expectedNet: float
    edgePct: float
    winProbPct: float             # the win probability the size was scaled by
    usagePct: float               # capitalRequired as % of the free capital at pick time


def usage_fraction(win_prob: float) -> float:
    """0 at a win probability <= 50% (minimum size) rising linearly to 1 at 100% sure (maximum size)."""
    return max(0.0, min(1.0, (win_prob - MIN_WIN_PROB) / (1.0 - MIN_WIN_PROB)))


MOMENTUM_SHORT_MULT = 0.5      # institutional review: noise-area momentum SHORT side evidence is weaker -> half size
OVERLAY_WITH_MULT, OVERLAY_AGAINST_MULT = 1.5, 0.5  # FII positioning overlay (only when the setting is on)


def size_multiplier(strategy: str | None, option_type: str, positioning_bias: int = 0,
                    overlay_enabled: bool = False) -> float:
    """Risk multiplier for one candidate (11 Nov 2026 institutional review, Strategies 2 and 4). Only the momentum
    engine (setups.SETUP_POLICY CORE / MERGED) is scaled; everything else stays 1.0."""
    from app.modules.opportunities.service.setups import SETUP_POLICY  # lazy: avoids a heavy import at module load

    if not strategy or SETUP_POLICY.get(strategy) not in ("CORE", "MERGED"):
        return 1.0
    m = MOMENTUM_SHORT_MULT if option_type == "PE" else 1.0
    if overlay_enabled and positioning_bias:
        with_bias = (option_type == "CE") == (positioning_bias > 0)
        m *= OVERLAY_WITH_MULT if with_bias else OVERLAY_AGAINST_MULT
    return m


def lots_for(entry: float, stop: float, lot_units: int, confidence: int, cap: CapitalState,
             size_mult: float = 1.0) -> tuple[int | None, str | None]:
    """Fixed-fractional lots: risk <= RISK_PER_TRADE_PCT x size_mult of capital, within free cash and the loss
    budget. `confidence` is accepted for call compatibility but no longer changes the size (see module docstring)."""
    del confidence
    risk_per_lot = (entry - stop) * lot_units
    premium_per_lot = entry * lot_units
    if risk_per_lot <= 0 or premium_per_lot <= 0:
        return None, "invalid levels"
    lots_by_budget = int(cap.remainingLossBudget // risk_per_lot)
    lots_by_cash = int(cap.availableCapital // premium_per_lot)
    if lots_by_budget < 1:
        return None, "loss budget below 1 lot"
    if lots_by_cash < 1:
        return None, "not enough free capital"
    lots_by_trade = int((cap.capital * RISK_PER_TRADE_PCT * max(0.0, size_mult) / 100.0) // risk_per_lot)
    if lots_by_trade < 1:
        if risk_per_lot > cap.capital * MAX_ONE_LOT_RISK_PCT / 100.0:
            return None, f"1 lot risks more than {MAX_ONE_LOT_RISK_PCT:g}% of capital"
        lots_by_trade = 1
    return min(lots_by_trade, lots_by_budget, lots_by_cash), None


def correlated_block(underlying: str, option_type: str, open_positions: list[tuple[str, str]],
                     max_same: int = MAX_SAME_DIRECTION_CORRELATED) -> str | None:
    """Why this candidate would over-concentrate the correlated index book, or None. `open_positions` =
    (underlyingCode, optionType) of RUNNING trades and LOCKED picks (plus anything already offered this pass)."""
    if underlying not in CORRELATED_INDEX_GROUP:
        return None
    same = sum(1 for u, t in open_positions if u in CORRELATED_INDEX_GROUP and t == option_type)
    if same >= max_same:
        side = "long (CE)" if option_type == "CE" else "short (PE)"
        return f"correlated index exposure: already {same} {side} position(s) across the index group"
    return None


def size_candidate(opp: dict[str, Any], cap: CapitalState) -> tuple[SizedCandidate | None, str | None]:
    """Sizes one saved opportunity for this session. Returns (sized, None) or (None, reason it was excluded)."""
    entry, stop, target = float(opp["entry"]), float(opp["stop"]), float(opp["target"])
    if not (stop < entry < target):
        return None, "invalid levels"
    lot_units = int(opp.get("lotUnits") or 0)
    if lot_units <= 0:
        return None, "unknown lot size"
    lots, why = lots_for(entry, stop, lot_units, int(opp["confidence"]), cap, float(opp.get("sizeMult") or 1.0))
    if lots is None:
        return None, why
    qty = lots * lot_units
    win_prob = max(0.0, min(1.0, int(opp["confidence"]) / 100.0))
    stop_pct = (entry - stop) / entry * 100
    margin_pct = (target - entry) / entry * 100
    cost = round_trip_cost_pct(entry, lot_units, opp.get("exchange") or "NSE", margin_pct)
    edge = expected_edge_pct(int(opp["confidence"]), margin_pct, stop_pct, cost)
    if edge <= 0:
        return None, "no positive edge after charges"
    return SizedCandidate(
        lots=lots, lotUnits=lot_units, quantity=qty, entryMax=round(entry_ceiling(entry, stop, target), 2),
        capitalRequired=round(qty * entry, 2), riskAmount=round(qty * (entry - stop), 2),
        rewardAmount=round(qty * (target - entry), 2), expectedNet=round(qty * entry * edge / 100.0, 2), edgePct=edge,
        winProbPct=round(win_prob * 100, 1), usagePct=round(qty * entry / cap.availableCapital * 100, 1),
    ), None


def rank_key(opp: dict[str, Any], sized: SizedCandidate) -> tuple[float, int, float, int]:
    """Best first: expected net rupees, then confidence, then reward:risk, then newest."""
    return (sized.expectedNet, int(opp["confidence"]), float(opp["rewardRisk"]), int(opp["id"]))
