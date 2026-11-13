from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.core.filter.base_filter import BaseFilter

PICK_STATE_VALUES = ("OFFERED", "LOCKED", "EXPIRED")


class SessionPickResponse(BaseModel):
    """One trade offered to the trader, sized to this session. Money fields are rupees; prices are option premium."""

    id: int
    sessionId: int
    opportunityId: int
    opportunityRef: str
    underlyingCode: str
    optionType: str
    strike: float
    expiry: str
    instrumentKey: Optional[str] = None
    strategy: Optional[str] = None
    traderCode: str = "ORB_WAVE_TRADER"
    traderName: str = "ORB & Momentum Wave Runner"
    confidence: int
    entry: float
    entryMax: float
    stop: float
    target: float
    stopPct: float
    targetPct: float
    rewardRisk: float
    lots: int
    lotUnits: int
    quantity: int
    capitalRequired: float
    riskAmount: float
    rewardAmount: float
    expectedNet: float
    capitalAtPick: float
    availableAtPick: float
    reasons: list[Any]
    risks: list[Any]
    pickState: str
    signalAt: datetime
    holdUntil: datetime
    offeredAt: datetime
    expiresAt: datetime
    lockedAt: Optional[datetime] = None
    lockedPrice: Optional[float] = None  # live premium when Trade Lock was pressed
    tradeId: Optional[int] = None        # ActiveTrade.id once entered
    winProbPct: float = 0.0              # win probability the size was scaled by (the opportunity's confidence)
    usagePct: float = 0.0                # share of the free capital this pick uses
    secondsLeft: float = 0.0  # seconds until the opportunity expires (0 once LOCKED / EXPIRED)
    createdAt: datetime


class SessionCapitalResponse(BaseModel):
    capital: float
    realizedPnl: float
    currentCapital: float
    committedPremium: float
    availableCapital: float
    maxLossAmount: float
    lossUsed: float
    committedRisk: float
    remainingLossBudget: float
    lockedTrades: int
    activeTradesCount: int = 0
    maxParallelTrades: int = 3
    activeTradeIds: list[int] = []


class SessionLoopResponse(BaseModel):
    """Result of one loop tick."""

    sessionId: int
    serverTime: datetime
    # SCHEDULED | PICK_READY | WAITING | HALTED | SESSION_CLOSED | UNSUPPORTED_TYPE
    state: str
    message: str
    picks: list[SessionPickResponse] = []  # open offers, best first: the rows of the session table
    lockedPicks: list[SessionPickResponse] = []  # LOCKED picks awaiting entry (SEMI_AUTO / MANUAL)
    capital: SessionCapitalResponse
    scanned: dict[str, Any]  # {"candidates": n, "excluded": {reason: n}}


class SessionPickSearchFilter(BaseFilter):
    """Search filter for a session's picks."""

    pickState: Optional[str] = None
