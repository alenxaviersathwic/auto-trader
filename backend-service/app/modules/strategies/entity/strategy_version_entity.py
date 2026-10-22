from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db.base_entity import BaseEntity

if TYPE_CHECKING:
    from app.modules.strategies.entity.strategy_entity import Strategy
    from app.modules.strategies.entity.strategy_rule_entity import StrategyRule


class StrategyVersion(BaseEntity):
    """
    Immutable version snapshot of a strategy definition.
    """

    __tablename__ = "strategy_versions"

    strategyId: Mapped[int] = mapped_column("strategy_id", BigInteger, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    versionNo: Mapped[int] = mapped_column("version_no", Integer, nullable=False)
    schemaVersion: Mapped[int] = mapped_column("schema_version", Integer, nullable=False, default=2)
    definition: Mapped[Dict[str, Any]] = mapped_column("definition", JSONB, nullable=False)
    contentHash: Mapped[str] = mapped_column("content_hash", String(64), nullable=False)
    changeNote: Mapped[Optional[str]] = mapped_column("change_note", String(300), nullable=True)

    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="versions")
    strategyRules: Mapped[List["StrategyRule"]] = relationship(
        "StrategyRule",
        back_populates="strategyVersion",
        cascade="all, delete-orphan",
        order_by="StrategyRule.sortOrder.asc()",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_strategy_versions_strat_ver_active",
            "strategy_id",
            "version_no",
            unique=True,
            postgresql_where=text("status = 1"),
        ),
    )
