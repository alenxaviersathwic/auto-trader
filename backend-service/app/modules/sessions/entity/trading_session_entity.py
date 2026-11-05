from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base_entity import BaseEntity


class TradingSession(BaseEntity):
    """
    A trading session: the capital / risk / scope / automation envelope the user sets up before
    trading. Execution and the day's risk-ledger guardrails (G-RISK-DAY, G-RISK-CONSEC,
    G-RISK-MAXTRADES, G-RISK-MAXCORRELATED -- see docs/04-risk-and-profit-management.md) operate
    inside exactly one session, and every order/position placed later carries a sessionId back
    to one of these rows.

    `status` (inherited from BaseEntity) is the soft-delete flag (ACTIVE/DELETED) -- unrelated to
    `sessionStatus` below, which is the session's own business lifecycle.
    """

    __tablename__ = "trading_sessions"

    name: Mapped[str] = mapped_column("name", String(150), nullable=False)
    tradeDate: Mapped[str] = mapped_column("trade_date", String(10), nullable=False)  # YYYY-MM-DD (IST)
    userId: Mapped[int] = mapped_column("user_id", BigInteger, nullable=False)

    capital: Mapped[float] = mapped_column("capital", Numeric(14, 2), nullable=False)
    maxLossPercentage: Mapped[float] = mapped_column(
        "max_loss_percentage", Numeric(5, 2), nullable=False, default=3.00
    )

    scope: Mapped[str] = mapped_column("scope", String(10), nullable=False)  # INDEX | COMMODITY
    underlyings: Mapped[list[str]] = mapped_column("underlyings", JSONB, nullable=False, default=list)
    commodityItems: Mapped[list[str]] = mapped_column("commodity_items", JSONB, nullable=False, default=list)

    sessionType: Mapped[str] = mapped_column(
        "session_type", String(12), nullable=False, default="MANUAL"
    )  # FULL_AUTO | SEMI_AUTO | MANUAL -- behaviour per type defined later
    routeThroughUpstox: Mapped[bool] = mapped_column(
        "route_through_upstox", Boolean, nullable=False, default=False
    )  # False = every order in this session is simulated; True = orders actually go to Upstox

    # Realised P&L of the session's closed trades (negative = loss). Written by the execution phase once it
    # exists; until then it stays 0, so currentCapital == capital.
    realizedPnl: Mapped[float] = mapped_column("realized_pnl", Numeric(14, 2), nullable=False, default=0)

    # Trading hours (IST day, stored UTC): nothing is offered before startAt; the loop closes the session at closeAt.
    startAt: Mapped[datetime] = mapped_column("start_at", DateTime(timezone=True), nullable=False)
    closeAt: Mapped[datetime] = mapped_column("close_at", DateTime(timezone=True), nullable=False)

    sessionStatus: Mapped[str] = mapped_column(
        "session_status", String(10), nullable=False, default="ACTIVE"
    )  # ACTIVE | CLOSED | EXPIRED
    haltReason: Mapped[str | None] = mapped_column("halt_reason", String(40), nullable=True)
    haltedAt: Mapped[datetime | None] = mapped_column("halted_at", DateTime(timezone=True), nullable=True)
    closedAt: Mapped[datetime | None] = mapped_column("closed_at", DateTime(timezone=True), nullable=True)
