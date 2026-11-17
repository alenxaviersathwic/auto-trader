from typing import Any, Dict, Optional
from sqlalchemy import BigInteger, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db.base_entity import BaseEntity


class MasterPreference(BaseEntity):
    __tablename__ = "master_preferences"

    key: Mapped[str] = mapped_column("key", String(80), nullable=False)
    value: Mapped[Dict[str, Any]] = mapped_column("value", JSONB, nullable=False)
    sourceMessageId: Mapped[Optional[int]] = mapped_column("source_message_id", BigInteger, nullable=True)

    __table_args__ = (
        Index("idx_master_preferences_key_active", "key", unique=True, postgresql_where=(BaseEntity.status == 1)),
    )
