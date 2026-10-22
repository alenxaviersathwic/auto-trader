from typing import Any
from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db.base_entity import BaseEntity


class MasterConfig(BaseEntity):
    __tablename__ = "master_configs"

    configKey: Mapped[str] = mapped_column("config_key", String(80), nullable=False)
    configValue: Mapped[Any] = mapped_column("config_value", JSONB, nullable=False)

    __table_args__ = (
        Index("idx_master_configs_key_active", "config_key", unique=True, postgresql_where=(BaseEntity.status == 1)),
    )
