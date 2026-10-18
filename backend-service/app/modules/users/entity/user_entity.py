from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base_entity import BaseEntity

if TYPE_CHECKING:
    from app.modules.users.entity.upstox_config_entity import UpstoxConfig


class User(BaseEntity):
    """
    User entity representing a trading user account.
    Extends BaseEntity (id, createdAt, status).
    """

    __tablename__ = "users"

    name: Mapped[str] = mapped_column("name", String(100), nullable=False)
    isDefault: Mapped[bool] = mapped_column(
        "is_default",
        Boolean,
        nullable=False,
        default=False,
    )

    # One-to-one relationship with UpstoxConfig
    upstoxConfig: Mapped[Optional["UpstoxConfig"]] = relationship(
        "UpstoxConfig",
        back_populates="user",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_users_name_active",
            "name",
            unique=True,
            postgresql_where=text("status = 1"),
        ),
    )
