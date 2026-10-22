from datetime import date
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import BigInteger, Boolean, Date, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db.base_entity import BaseEntity

if TYPE_CHECKING:
    from app.modules.strategies.entity.rule_version_entity import RuleVersion


class Rule(BaseEntity):
    """
    Guardrail or condition block rule entity.
    """

    __tablename__ = "rules"

    code: Mapped[str] = mapped_column("code", String(80), nullable=False)
    name: Mapped[str] = mapped_column("name", String(150), nullable=False)
    ruleKind: Mapped[str] = mapped_column("rule_kind", String(15), nullable=False)
    ruleType: Mapped[str] = mapped_column("rule_type", String(25), nullable=False)
    action: Mapped[Optional[str]] = mapped_column("action", String(10), nullable=True)
    priority: Mapped[str] = mapped_column("priority", String(8), nullable=False, default="MEDIUM")
    appliesTo: Mapped[Dict[str, Any]] = mapped_column("applies_to", JSONB, nullable=False, default=dict)
    conditionText: Mapped[str] = mapped_column("condition_text", Text, nullable=False)
    currentVersionId: Mapped[Optional[int]] = mapped_column("current_version_id", BigInteger, nullable=True)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column("evidence", JSONB, nullable=True)
    reviewBy: Mapped[Optional[date]] = mapped_column("review_by", Date, nullable=True)
    executable: Mapped[bool] = mapped_column("executable", Boolean, nullable=False, default=False)
    reviewFlags: Mapped[Optional[List[str]]] = mapped_column("review_flags", JSONB, nullable=True)
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column("provenance", JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column("enabled", Boolean, nullable=False, default=True)

    versions: Mapped[List["RuleVersion"]] = relationship(
        "RuleVersion",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="RuleVersion.versionNo.desc()",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_rules_code_active",
            "code",
            unique=True,
            postgresql_where=text("status = 1"),
        ),
    )

    @property
    def isStale(self) -> bool:
        if self.reviewBy and self.reviewBy < date.today():
            return True
        return False
