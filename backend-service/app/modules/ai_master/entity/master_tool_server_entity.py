from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db.base_entity import BaseEntity


class MasterToolServer(BaseEntity):
    __tablename__ = "master_tool_servers"

    name: Mapped[str] = mapped_column("name", String(60), nullable=False)
    transport: Mapped[str] = mapped_column("transport", String(10), nullable=False, default="HTTP")  # HTTP or STDIO
    url: Mapped[Optional[str]] = mapped_column("url", String(300), nullable=True)
    authRef: Mapped[Optional[str]] = mapped_column("auth_ref", String(60), nullable=True)
    tierCap: Mapped[str] = mapped_column("tier_cap", String(10), nullable=False, default="PROPOSE")  # READ, ANALYZE, PROPOSE, OPERATE
    enabled: Mapped[bool] = mapped_column("enabled", Boolean, nullable=False, default=True)
    lastSeenAt: Mapped[Optional[datetime]] = mapped_column("last_seen_at", DateTime(timezone=True), nullable=True)
    lastError: Mapped[Optional[str]] = mapped_column("last_error", String(300), nullable=True)
    toolCount: Mapped[int] = mapped_column("tool_count", Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_master_tool_servers_name_active", "name", unique=True, postgresql_where=(BaseEntity.status == 1)),
    )
