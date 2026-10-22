from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db.base_entity import BaseEntity


class MasterToolPolicy(BaseEntity):
    __tablename__ = "master_tool_policies"

    serverName: Mapped[str] = mapped_column("server_name", String(60), nullable=False)
    toolName: Mapped[str] = mapped_column("tool_name", String(80), nullable=False)
    tier: Mapped[str] = mapped_column("tier", String(10), nullable=False)
    enabled: Mapped[bool] = mapped_column("enabled", Boolean, nullable=False, default=True)
    autoApprove: Mapped[bool] = mapped_column("auto_approve", Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_master_tool_policies_server_tool_active", "server_name", "tool_name", unique=True, postgresql_where=(BaseEntity.status == 1)),
    )
