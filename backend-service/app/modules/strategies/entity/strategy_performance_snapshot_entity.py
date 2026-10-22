from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db.base_entity import BaseEntity

if TYPE_CHECKING:
    from app.modules.strategies.entity.strategy_entity import Strategy


class StrategyPerformanceSnapshot(BaseEntity):
    """
    Performance snapshot for a strategy by source (LEGACY_IMPORT, PAPER, LIVE, BACKTEST).
    """

    __tablename__ = "strategy_performance_snapshots"

    strategyId: Mapped[int] = mapped_column(
        "strategy_id",
        BigInteger,
        ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False,
    )
    versionNo: Mapped[Optional[int]] = mapped_column("version_no", Integer, nullable=True)
    source: Mapped[str] = mapped_column("source", String(15), nullable=False)
    domain: Mapped[str] = mapped_column("domain", String(10), nullable=False, default="UNKNOWN")
    periodFrom: Mapped[Optional[date]] = mapped_column("period_from", Date, nullable=True)
    periodTo: Mapped[Optional[date]] = mapped_column("period_to", Date, nullable=True)
    asOf: Mapped[Optional[datetime]] = mapped_column("as_of", DateTime(timezone=True), nullable=True)
    totalTrades: Mapped[int] = mapped_column("total_trades", Integer, nullable=False, default=0)
    winningTrades: Mapped[int] = mapped_column("winning_trades", Integer, nullable=False, default=0)
    losingTrades: Mapped[int] = mapped_column("losing_trades", Integer, nullable=False, default=0)
    winRatePct: Mapped[Decimal] = mapped_column("win_rate_pct", Numeric(6, 2), nullable=False, default=Decimal("0.00"))
    netPnl: Mapped[Decimal] = mapped_column("net_pnl", Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    profitFactor: Mapped[Decimal] = mapped_column("profit_factor", Numeric(8, 2), nullable=False, default=Decimal("0.00"))
    maxDrawdown: Mapped[Decimal] = mapped_column("max_drawdown", Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    legacyHealth: Mapped[Optional[str]] = mapped_column("legacy_health", String(10), nullable=True)
    reliabilityFlags: Mapped[Optional[List[str]]] = mapped_column("reliability_flags", JSONB, nullable=True)

    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="performanceSnapshots")
