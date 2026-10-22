from typing import Any, Dict
from sqlalchemy import Boolean, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db.base_entity import BaseEntity


class HealthPolicy(BaseEntity):
    """
    Health policy evaluating strategy performance against thresholds.
    """

    __tablename__ = "health_policies"

    code: Mapped[str] = mapped_column("code", String(60), nullable=False)
    name: Mapped[str] = mapped_column("name", String(120), nullable=False)
    scope: Mapped[Any] = mapped_column("scope", JSONB, nullable=False, default="ALL")
    params: Mapped[Dict[str, Any]] = mapped_column("params", JSONB, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column("enabled", Boolean, nullable=False, default=True)

    __table_args__ = (
        Index(
            "ix_health_policies_code_active",
            "code",
            unique=True,
            postgresql_where=text("status = 1"),
        ),
    )
