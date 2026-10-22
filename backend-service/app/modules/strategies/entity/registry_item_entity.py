from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db.base_entity import BaseEntity


class RegistryItem(BaseEntity):
    """
    Registry item entity representing extensible catalog elements:
    INDICATOR, OPERATOR, OPERAND_SOURCE, STRIKE_SELECTOR, STOP_TYPE, TARGET_TYPE,
    TRAIL_TYPE, EXPIRY_CYCLE, LEG_ACTION, ADJUSTMENT_ACTION, STRUCTURE, EVALUATOR, MARKET.
    """

    __tablename__ = "registry_items"

    registryType: Mapped[str] = mapped_column("registry_type", String(30), nullable=False)
    code: Mapped[str] = mapped_column("code", String(60), nullable=False)
    name: Mapped[str] = mapped_column("name", String(120), nullable=False)
    kind: Mapped[str] = mapped_column("kind", String(10), nullable=False, default="BUILT_IN")
    version: Mapped[int] = mapped_column("version", Integer, nullable=False, default=1)
    schema: Mapped[Optional[Dict[str, Any]]] = mapped_column("schema", JSONB, nullable=True)
    expression: Mapped[Optional[Dict[str, Any]]] = mapped_column("expression", JSONB, nullable=True)
    handlerKey: Mapped[Optional[str]] = mapped_column("handler_key", String(80), nullable=True)
    executable: Mapped[bool] = mapped_column("executable", Boolean, nullable=False, default=False)
    requires: Mapped[Optional[List[str]]] = mapped_column("requires", JSONB, nullable=True)
    description: Mapped[Optional[str]] = mapped_column("description", Text, nullable=True)
    enabled: Mapped[bool] = mapped_column("enabled", Boolean, nullable=False, default=True)

    __table_args__ = (
        Index(
            "ix_registry_items_type_code_active",
            "registry_type",
            "code",
            unique=True,
            postgresql_where=text("status = 1"),
        ),
    )
