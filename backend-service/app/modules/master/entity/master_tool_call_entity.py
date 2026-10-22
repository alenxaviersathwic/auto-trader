from typing import Any, Dict, Optional
from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db.base_entity import BaseEntity


class MasterToolCall(BaseEntity):
    __tablename__ = "master_tool_calls"

    runId: Mapped[int] = mapped_column("run_id", BigInteger, ForeignKey("master_runs.id"), nullable=False, index=True)
    serverName: Mapped[str] = mapped_column("server_name", String(60), nullable=False)
    toolName: Mapped[str] = mapped_column("tool_name", String(80), nullable=False)
    tier: Mapped[str] = mapped_column("tier", String(10), nullable=False)  # READ, ANALYZE, PROPOSE, OPERATE
    arguments: Mapped[Optional[Dict[str, Any]]] = mapped_column("arguments", JSONB, nullable=True)
    resultSummary: Mapped[Optional[Dict[str, Any]]] = mapped_column("result_summary", JSONB, nullable=True)
    callStatus: Mapped[str] = mapped_column("call_status", String(10), nullable=False)  # OK, ERROR, DENIED, TIMEOUT
    durationMs: Mapped[int] = mapped_column("duration_ms", Integer, nullable=False, default=0)
