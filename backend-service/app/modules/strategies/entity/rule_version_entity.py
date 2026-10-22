from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db.base_entity import BaseEntity

if TYPE_CHECKING:
    from app.modules.strategies.entity.rule_entity import Rule


class RuleVersion(BaseEntity):
    """
    Immutable version snapshot of rule content.
    """

    __tablename__ = "rule_versions"

    ruleId: Mapped[int] = mapped_column("rule_id", BigInteger, ForeignKey("rules.id", ondelete="CASCADE"), nullable=False)
    versionNo: Mapped[int] = mapped_column("version_no", Integer, nullable=False)
    content: Mapped[Dict[str, Any]] = mapped_column("content", JSONB, nullable=False)
    changeNote: Mapped[Optional[str]] = mapped_column("change_note", String(300), nullable=True)

    rule: Mapped["Rule"] = relationship("Rule", back_populates="versions")

    __table_args__ = (
        Index(
            "ix_rule_versions_rule_ver_active",
            "rule_id",
            "version_no",
            unique=True,
            postgresql_where=text("status = 1"),
        ),
    )
