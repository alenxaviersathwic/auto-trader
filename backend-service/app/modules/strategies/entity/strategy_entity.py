from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import BigInteger, Boolean, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db.base_entity import BaseEntity

if TYPE_CHECKING:
    from app.modules.strategies.entity.strategy_version_entity import StrategyVersion
    from app.modules.strategies.entity.strategy_performance_snapshot_entity import StrategyPerformanceSnapshot
    from app.modules.strategies.entity.strategy_health_event_entity import StrategyHealthEvent


class Strategy(BaseEntity):
    """
    Strategy master entity.
    """

    __tablename__ = "strategies"

    code: Mapped[str] = mapped_column("code", String(80), nullable=False)
    name: Mapped[str] = mapped_column("name", String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column("description", Text, nullable=True)
    category: Mapped[str] = mapped_column("category", String(20), nullable=False)
    structure: Mapped[Optional[str]] = mapped_column("structure", String(30), nullable=True)
    bias: Mapped[Optional[str]] = mapped_column("bias", String(10), nullable=True)
    optionSide: Mapped[Optional[str]] = mapped_column("option_side", String(5), nullable=True)
    markets: Mapped[List[str]] = mapped_column("markets", JSONB, nullable=False, default=list)
    underlyingTypes: Mapped[List[str]] = mapped_column("underlying_types", JSONB, nullable=False, default=list)
    exchange: Mapped[Optional[str]] = mapped_column("exchange", String(10), nullable=True)
    tradingModes: Mapped[List[str]] = mapped_column("trading_modes", JSONB, nullable=False, default=list)
    executionModes: Mapped[List[str]] = mapped_column("execution_modes", JSONB, nullable=False, default=list)
    timeframe: Mapped[Optional[str]] = mapped_column("timeframe", String(10), nullable=True)
    definitionFormat: Mapped[str] = mapped_column("definition_format", String(10), nullable=False, default="RULE_TREE")
    executable: Mapped[bool] = mapped_column("executable", Boolean, nullable=False, default=False)
    lifecycleStatus: Mapped[str] = mapped_column("lifecycle_status", String(12), nullable=False, default="DRAFT")
    health: Mapped[str] = mapped_column("health", String(10), nullable=False, default="UNKNOWN")
    healthOverride: Mapped[Optional[str]] = mapped_column("health_override", String(10), nullable=True)
    healthOverrideReason: Mapped[Optional[str]] = mapped_column("health_override_reason", String(255), nullable=True)
    healthOverrideUntil: Mapped[Optional[datetime]] = mapped_column("health_override_until", DateTime(timezone=True), nullable=True)
    validationStatus: Mapped[str] = mapped_column("validation_status", String(15), nullable=False, default="UNTESTED")
    enabled: Mapped[bool] = mapped_column("enabled", Boolean, nullable=False, default=True)
    riskProfile: Mapped[Optional[Dict[str, Any]]] = mapped_column("risk_profile", JSONB, nullable=True)
    references: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column("references", JSONB, nullable=True)
    riskNotes: Mapped[Optional[List[str]]] = mapped_column("risk_notes", JSONB, nullable=True)
    howItWorks: Mapped[Optional[List[Dict[str, str]]]] = mapped_column("how_it_works", JSONB, nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column("tags", JSONB, nullable=True)
    attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column("attributes", JSONB, nullable=True)
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column("provenance", JSONB, nullable=True)
    reviewFlags: Mapped[Optional[List[str]]] = mapped_column("review_flags", JSONB, nullable=True)
    currentVersionId: Mapped[Optional[int]] = mapped_column("current_version_id", BigInteger, nullable=True)

    # Relationships
    versions: Mapped[List["StrategyVersion"]] = relationship(
        "StrategyVersion",
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="StrategyVersion.versionNo.desc()",
        lazy="selectin",
    )
    performanceSnapshots: Mapped[List["StrategyPerformanceSnapshot"]] = relationship(
        "StrategyPerformanceSnapshot",
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="StrategyPerformanceSnapshot.createdAt.desc()",
        lazy="selectin",
    )
    healthEvents: Mapped[List["StrategyHealthEvent"]] = relationship(
        "StrategyHealthEvent",
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="StrategyHealthEvent.createdAt.desc()",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_strategies_code_active",
            "code",
            unique=True,
            postgresql_where=text("status = 1"),
        ),
    )

    @property
    def effectiveHealth(self) -> str:
        if self.healthOverride:
            if not self.healthOverrideUntil or datetime.now(self.healthOverrideUntil.tzinfo or None) < self.healthOverrideUntil:
                return self.healthOverride
        return self.health

    @property
    def suggestable(self) -> bool:
        return (
            self.enabled
            and self.executable
            and self.lifecycleStatus == "ACTIVE"
            and self.effectiveHealth != "SUSPENDED"
            and self.validationStatus != "REJECTED"
        )
