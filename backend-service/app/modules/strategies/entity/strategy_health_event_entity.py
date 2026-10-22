from typing import TYPE_CHECKING, Optional
from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db.base_entity import BaseEntity

if TYPE_CHECKING:
    from app.modules.strategies.entity.strategy_entity import Strategy


class StrategyHealthEvent(BaseEntity):
    """
    Audit log of strategy health state transitions.
    """

    __tablename__ = "strategy_health_events"

    strategyId: Mapped[int] = mapped_column(
        "strategy_id",
        BigInteger,
        ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False,
    )
    fromHealth: Mapped[str] = mapped_column("from_health", String(10), nullable=False)
    toHealth: Mapped[str] = mapped_column("to_health", String(10), nullable=False)
    reason: Mapped[str] = mapped_column("reason", String(255), nullable=False)
    snapshotId: Mapped[Optional[int]] = mapped_column("snapshot_id", BigInteger, nullable=True)
    triggeredBy: Mapped[str] = mapped_column("triggered_by", String(10), nullable=False, default="POLICY")

    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="healthEvents")
