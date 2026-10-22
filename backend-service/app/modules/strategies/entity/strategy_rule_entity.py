from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db.base_entity import BaseEntity

if TYPE_CHECKING:
    from app.modules.strategies.entity.strategy_version_entity import StrategyVersion
    from app.modules.strategies.entity.rule_entity import Rule


class StrategyRule(BaseEntity):
    """
    Association entity between a strategy version and condition block rules.
    """

    __tablename__ = "strategy_rules"

    strategyVersionId: Mapped[int] = mapped_column(
        "strategy_version_id",
        BigInteger,
        ForeignKey("strategy_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    ruleId: Mapped[int] = mapped_column("rule_id", BigInteger, nullable=False)
    role: Mapped[str] = mapped_column("role", String(20), nullable=False)
    required: Mapped[bool] = mapped_column("required", Boolean, nullable=False, default=True)
    weight: Mapped[int] = mapped_column("weight", Integer, nullable=False, default=1)
    sortOrder: Mapped[int] = mapped_column("sort_order", Integer, nullable=False, default=0)
    paramOverrides: Mapped[Optional[Dict[str, Any]]] = mapped_column("param_overrides", JSONB, nullable=True)

    strategyVersion: Mapped["StrategyVersion"] = relationship("StrategyVersion", back_populates="strategyRules")
