from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.filter.base_filter import BaseFilter


class TradeCreateRequest(BaseModel):
    """Payload for entering a locked pick and starting its dedicated Trader loop."""

    sessionId: int = Field(..., gt=0)
    pickId: int = Field(..., gt=0)
    entryAt: Optional[float] = Field(default=None, gt=0, description="Actual entry fill price; defaults to lockedPrice or planned entry")
    lots: Optional[int] = Field(default=None, ge=1, description="Lots to take; defaults to risk-based suggested lots")
    initialStop: Optional[float] = Field(default=None, gt=0)
    initialTarget: Optional[float] = Field(default=None, gt=0)


class TradeAdjustRequest(BaseModel):
    """Manual override of currentStop and/or currentTarget while the trade is RUNNING."""

    currentStop: Optional[float] = Field(default=None, gt=0)
    currentTarget: Optional[float] = Field(default=None, gt=0)
    reason: Optional[str] = Field(default=None, max_length=200)


class TradeExitRequest(BaseModel):
    """Manual exit / square-off request."""

    exitPrice: Optional[float] = Field(default=None, gt=0)
    reason: Optional[str] = Field(default="MANUAL_EXIT", max_length=40)


class LotSuggestionResponse(BaseModel):
    """Risk- and capital-based lot suggestion for a given entry price (`entryAt`)."""

    sessionId: int
    pickId: int
    entryAt: float
    stop: float
    target: float
    entryMax: float
    lotUnits: int
    suggestedLots: int
    maxLotsByCash: int
    maxLotsByRisk: int
    maxAffordableLots: int
    quantity: int
    capitalRequired: float
    riskAmount: float
    rewardAmount: float
    expectedNet: float
    availableCapital: float
    remainingLossBudget: float
    winProbPct: float
    activeTradesCount: int
    maxParallelTrades: int
    canEnter: bool
    blockReason: Optional[str] = None


class TradeResponse(BaseModel):
    """Full representation of an ActiveTrade."""

    id: int
    sessionId: int
    pickId: int
    opportunityId: int
    opportunityRef: str
    userId: int
    underlyingCode: str
    optionType: str
    strike: float
    expiry: str
    instrumentKey: Optional[str] = None
    strategy: Optional[str] = None
    confidence: int
    winRatePct: float
    traderProfile: str
    sessionType: str
    routeThroughUpstox: bool
    lots: int
    lotUnits: int
    quantity: int
    plannedEntry: float
    entryAt: float
    capitalUsed: float
    initialStop: float
    initialTarget: float
    currentStop: float
    currentTarget: float
    lastPrice: float
    peakPrice: float
    troughPrice: float
    entryOrderId: Optional[str] = None
    exitOrderId: Optional[str] = None
    brokerStatus: str
    brokerError: Optional[str] = None
    tradeState: str
    exitReason: Optional[str] = None
    exitPrice: Optional[float] = None
    grossPnl: float
    charges: float
    netPnl: float
    pnlPct: float
    enteredAt: datetime
    exitedAt: Optional[datetime] = None
    holdUntil: datetime
    trailEvents: list[dict[str, Any]] = []
    marketTelemetry: dict[str, Any] = {}
    candles1m: list[dict[str, Any]] = []
    status: str
    createdAt: datetime


class TradeLiveSnapshot(BaseModel):
    """SSE payload pushed whenever the trade's price, SL, Target, telemetry, or state updates."""

    tradeId: int
    serverTime: datetime
    trade: TradeResponse


class TradeSearchFilter(BaseFilter):
    """Paginated search filter for trades."""

    sessionId: Optional[int] = None
    underlyingCode: Optional[str] = None
    tradeState: Optional[str] = None
    traderProfile: Optional[str] = None

