from datetime import datetime
from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from app.core.db.entity_status import EntityStatus
from app.core.db.status_type import StatusType


class Base(DeclarativeBase):
    pass


class BaseEntity(Base):
    """
    Abstract base entity for all models in auto-trader.
    Includes:
    - id: BigInteger primary key
    - createdAt: created_at timestamp with timezone, server-generated
    - status: status smallint (1=ACTIVE, 0=DELETED), mapped to EntityStatus
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    createdAt: Mapped[datetime] = mapped_column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status: Mapped[EntityStatus] = mapped_column(
        "status",
        StatusType,
        nullable=False,
        default=EntityStatus.ACTIVE,
    )
