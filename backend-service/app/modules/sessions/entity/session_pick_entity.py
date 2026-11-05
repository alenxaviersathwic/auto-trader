from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base_entity import BaseEntity


class _PickColumns:
    """Columns of one offered trade. Shared by the live table and its end-of-day archive, so they cannot drift."""

    sessionId: Mapped[int] = mapped_column("session_id", BigInteger, nullable=False, index=True)
    opportunityId: Mapped[int] = mapped_column("opportunity_id", BigInteger, nullable=False)
    opportunityRef: Mapped[str] = mapped_column("opportunity_ref", String(48), nullable=False)

    underlyingCode: Mapped[str] = mapped_column("underlying_code", String(30), nullable=False)
    optionType: Mapped[str] = mapped_column("option_type", String(2), nullable=False)  # CE | PE
    strike: Mapped[float] = mapped_column("strike", Numeric(12, 2), nullable=False)
    expiry: Mapped[str] = mapped_column("expiry", String(10), nullable=False)
    instrumentKey: Mapped[str | None] = mapped_column("instrument_key", String(80), nullable=True)
    strategy: Mapped[str | None] = mapped_column("strategy", String(100), nullable=True)
    confidence: Mapped[int] = mapped_column("confidence", SmallInteger, nullable=False)

    entry: Mapped[float] = mapped_column("entry", Numeric(12, 2), nullable=False)
    entryMax: Mapped[float] = mapped_column("entry_max", Numeric(12, 2), nullable=False)  # do not chase above this
    stop: Mapped[float] = mapped_column("stop", Numeric(12, 2), nullable=False)
    target: Mapped[float] = mapped_column("target", Numeric(12, 2), nullable=False)
    rewardRisk: Mapped[float] = mapped_column("reward_risk", Numeric(6, 2), nullable=False)

    lots: Mapped[int] = mapped_column("lots", Integer, nullable=False)
    lotUnits: Mapped[int] = mapped_column("lot_units", Integer, nullable=False)
    quantity: Mapped[int] = mapped_column("quantity", Integer, nullable=False)
    capitalRequired: Mapped[float] = mapped_column("capital_required", Numeric(14, 2), nullable=False)
    riskAmount: Mapped[float] = mapped_column("risk_amount", Numeric(14, 2), nullable=False)
    rewardAmount: Mapped[float] = mapped_column("reward_amount", Numeric(14, 2), nullable=False)
    expectedNet: Mapped[float] = mapped_column("expected_net", Numeric(14, 2), nullable=False)
    capitalAtPick: Mapped[float] = mapped_column("capital_at_pick", Numeric(14, 2), nullable=False)
    availableAtPick: Mapped[float] = mapped_column("available_at_pick", Numeric(14, 2), nullable=False)

    reasons: Mapped[list[Any]] = mapped_column("reasons", JSONB, nullable=False, default=list)
    risks: Mapped[list[Any]] = mapped_column("risks", JSONB, nullable=False, default=list)

    pickState: Mapped[str] = mapped_column("pick_state", String(10), nullable=False, default="OFFERED")
    signalAt: Mapped[datetime] = mapped_column("signal_at", DateTime(timezone=True), nullable=False)
    holdUntil: Mapped[datetime] = mapped_column("hold_until", DateTime(timezone=True), nullable=False)
    offeredAt: Mapped[datetime] = mapped_column("offered_at", DateTime(timezone=True), nullable=False)
    expiresAt: Mapped[datetime] = mapped_column("expires_at", DateTime(timezone=True), nullable=False)
    lockedAt: Mapped[datetime | None] = mapped_column("locked_at", DateTime(timezone=True), nullable=True)
    lockedPrice: Mapped[float | None] = mapped_column("locked_price", Numeric(12, 2), nullable=True)  # live premium at lock


class SessionPick(_PickColumns, BaseEntity):
    """
    The single trade a session offers to the trader on one loop tick.

    It is a SNAPSHOT of an already-created opportunity, sized to the session's own capital and loss
    budget at that moment. `pickState`: OFFERED (its opportunity is still valid) -> LOCKED (trader
    pressed Trade Lock in time) or EXPIRED (the opportunity expired first). What happens after LOCKED is
    defined later; nothing here places an order.
    """

    __tablename__ = "session_picks"


class SessionPickArchive(_PickColumns, BaseEntity):
    """
    Picks of finished sessions, moved out of `session_picks` by the daily 16:00 IST job so the live table the loop
    queries every second starts each day empty. Same columns; a pick that was still OFFERED is stored as EXPIRED.
    """

    __tablename__ = "session_picks_archive"

    archivedAt: Mapped[datetime] = mapped_column(
        "archived_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
