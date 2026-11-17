from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base_entity import BaseEntity


class SetupScorecard(BaseEntity):
    """Rolling results of one setup for one session manager (service/learning_rules.py scorecard()). A PAUSED setup
    is not traded in that manager's sessions."""

    __tablename__ = "setup_scorecards"

    setup: Mapped[str] = mapped_column("setup", String(100), nullable=False)
    # the session manager whose autopsy sub-agent owns this row (FIB_GOLDEN_TRADER | FLOW_MOMENTUM_TRADER)
    managerCode: Mapped[str] = mapped_column("manager_code", String(40), nullable=False, index=True)
    policy: Mapped[str | None] = mapped_column("policy", String(24), nullable=True)
    closedTrades: Mapped[int] = mapped_column("closed_trades", Integer, nullable=False, default=0)
    wins: Mapped[int] = mapped_column("wins", Integer, nullable=False, default=0)
    losses: Mapped[int] = mapped_column("losses", Integer, nullable=False, default=0)
    netPnl: Mapped[float] = mapped_column("net_pnl", Numeric(14, 2), nullable=False, default=0)
    avgR: Mapped[float] = mapped_column("avg_r", Numeric(8, 2), nullable=False, default=0)
    winRatePct: Mapped[float] = mapped_column("win_rate_pct", Numeric(6, 1), nullable=False, default=0)
    expectancy: Mapped[float] = mapped_column("expectancy", Numeric(14, 2), nullable=False, default=0)
    # ACTIVE | PAUSED (named scoreStatus: BaseEntity already owns `status`, the soft-delete flag)
    scoreStatus: Mapped[str] = mapped_column("score_status", String(10), nullable=False, default="ACTIVE")
    statusReason: Mapped[str | None] = mapped_column("status_reason", String(300), nullable=True)
    pausedAt: Mapped[datetime | None] = mapped_column("paused_at", DateTime(timezone=True), nullable=True)
    resumedAt: Mapped[datetime | None] = mapped_column("resumed_at", DateTime(timezone=True), nullable=True)
    lastTradeId: Mapped[int | None] = mapped_column("last_trade_id", BigInteger, nullable=True)
    updatedAt: Mapped[datetime | None] = mapped_column("updated_at", DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("uq_setup_scorecards_manager_setup", "manager_code", "setup", unique=True,
              postgresql_where=text("status = 1")),
    )
