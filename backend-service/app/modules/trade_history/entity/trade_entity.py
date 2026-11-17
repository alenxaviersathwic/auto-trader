from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base_entity import BaseEntity


class ActiveTrade(BaseEntity):
    """
    A locked pick that has been entered and handed over to its own dedicated Trader loop (`trade-pilot-{id}`).
    Tracks live option price, dynamically ratcheted Stop-Loss and Target levels, Upstox broker order IDs,
    real-time microstructure telemetry, and the chronological decision log (`trailEvents`).
    """

    __tablename__ = "active_trades"

    sessionId: Mapped[int] = mapped_column("session_id", BigInteger, nullable=False, index=True)
    pickId: Mapped[int] = mapped_column("pick_id", BigInteger, nullable=False)
    opportunityId: Mapped[int] = mapped_column("opportunity_id", BigInteger, nullable=False)
    opportunityRef: Mapped[str] = mapped_column("opportunity_ref", String(48), nullable=False)
    userId: Mapped[int] = mapped_column("user_id", BigInteger, nullable=False)

    underlyingCode: Mapped[str] = mapped_column("underlying_code", String(30), nullable=False)
    optionType: Mapped[str] = mapped_column("option_type", String(2), nullable=False)
    strike: Mapped[float] = mapped_column("strike", Numeric(12, 2), nullable=False)
    expiry: Mapped[str] = mapped_column("expiry", String(10), nullable=False)
    instrumentKey: Mapped[str | None] = mapped_column("instrument_key", String(80), nullable=True)
    strategy: Mapped[str | None] = mapped_column("strategy", String(100), nullable=True)
    confidence: Mapped[int] = mapped_column("confidence", SmallInteger, nullable=False)
    winRatePct: Mapped[float] = mapped_column("win_rate_pct", Numeric(6, 2), nullable=False, default=50.0)
    traderProfile: Mapped[str] = mapped_column(
        "trader_profile", String(24), nullable=False, default="STEP_GUARD"
    )  # HIGH_CONVICTION | STEP_GUARD
    sessionType: Mapped[str] = mapped_column("session_type", String(12), nullable=False, default="MANUAL")
    routeThroughUpstox: Mapped[bool] = mapped_column("route_through_upstox", Boolean, nullable=False, default=False)

    lots: Mapped[int] = mapped_column("lots", Integer, nullable=False)
    lotUnits: Mapped[int] = mapped_column("lot_units", Integer, nullable=False)
    quantity: Mapped[int] = mapped_column("quantity", Integer, nullable=False)
    plannedEntry: Mapped[float] = mapped_column("planned_entry", Numeric(12, 2), nullable=False)
    entryAt: Mapped[float] = mapped_column("entry_at", Numeric(12, 2), nullable=False)
    capitalUsed: Mapped[float] = mapped_column("capital_used", Numeric(14, 2), nullable=False)

    initialStop: Mapped[float] = mapped_column("initial_stop", Numeric(12, 2), nullable=False)
    initialTarget: Mapped[float] = mapped_column("initial_target", Numeric(12, 2), nullable=False)
    currentStop: Mapped[float] = mapped_column("current_stop", Numeric(12, 2), nullable=False)
    currentTarget: Mapped[float] = mapped_column("current_target", Numeric(12, 2), nullable=False)
    lastPrice: Mapped[float] = mapped_column("last_price", Numeric(12, 2), nullable=False)
    peakPrice: Mapped[float] = mapped_column("peak_price", Numeric(12, 2), nullable=False)
    troughPrice: Mapped[float] = mapped_column("trough_price", Numeric(12, 2), nullable=False)

    entryOrderId: Mapped[str | None] = mapped_column("entry_order_id", String(80), nullable=True)
    exitOrderId: Mapped[str | None] = mapped_column("exit_order_id", String(80), nullable=True)
    brokerStatus: Mapped[str] = mapped_column("broker_status", String(20), nullable=False, default="SIMULATED")
    brokerError: Mapped[str | None] = mapped_column("broker_error", String(500), nullable=True)

    tradeState: Mapped[str] = mapped_column("trade_state", String(16), nullable=False, default="RUNNING")
    exitReason: Mapped[str | None] = mapped_column("exit_reason", String(32), nullable=True)
    exitPrice: Mapped[float | None] = mapped_column("exit_price", Numeric(12, 2), nullable=True)
    grossPnl: Mapped[float] = mapped_column("gross_pnl", Numeric(14, 2), nullable=False, default=0)
    charges: Mapped[float] = mapped_column("charges", Numeric(14, 2), nullable=False, default=0)
    netPnl: Mapped[float] = mapped_column("net_pnl", Numeric(14, 2), nullable=False, default=0)
    pnlPct: Mapped[float] = mapped_column("pnl_pct", Numeric(8, 2), nullable=False, default=0)

    enteredAt: Mapped[datetime] = mapped_column("entered_at", DateTime(timezone=True), nullable=False)
    exitedAt: Mapped[datetime | None] = mapped_column("exited_at", DateTime(timezone=True), nullable=True)
    holdUntil: Mapped[datetime] = mapped_column("hold_until", DateTime(timezone=True), nullable=False)

    trailEvents: Mapped[list[ dict[str, Any]]] = mapped_column("trail_events", JSONB, nullable=False, default=list)
    marketTelemetry: Mapped[dict[str, Any]] = mapped_column("market_telemetry", JSONB, nullable=False, default=dict)

