from typing import Any

from sqlalchemy import BigInteger, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base_entity import BaseEntity


class TradeAutopsy(BaseEntity):
    """What one finished trade did and what it taught (service/autopsy_agent.py). One row per trade."""

    __tablename__ = "trade_autopsies"

    tradeId: Mapped[int] = mapped_column("trade_id", BigInteger, nullable=False)
    sessionId: Mapped[int] = mapped_column("session_id", BigInteger, nullable=False, index=True)
    setup: Mapped[str] = mapped_column("setup", String(100), nullable=False, index=True)
    traderCode: Mapped[str | None] = mapped_column("trader_code", String(40), nullable=True)
    underlyingCode: Mapped[str] = mapped_column("underlying_code", String(30), nullable=False)
    optionType: Mapped[str] = mapped_column("option_type", String(2), nullable=False)
    outcome: Mapped[str] = mapped_column("outcome", String(8), nullable=False)  # WIN | LOSS
    verdict: Mapped[str] = mapped_column("verdict", String(24), nullable=False)
    rMultiple: Mapped[float] = mapped_column("r_multiple", Numeric(8, 2), nullable=False)
    mfeR: Mapped[float] = mapped_column("mfe_r", Numeric(8, 2), nullable=False)
    maeR: Mapped[float] = mapped_column("mae_r", Numeric(8, 2), nullable=False)
    givebackPct: Mapped[float | None] = mapped_column("giveback_pct", Numeric(8, 1), nullable=True)
    netPnl: Mapped[float] = mapped_column("net_pnl", Numeric(14, 2), nullable=False)
    plannedTargetPct: Mapped[float | None] = mapped_column("planned_target_pct", Numeric(8, 2), nullable=True)
    tags: Mapped[list[str]] = mapped_column("tags", JSONB, nullable=False, default=list)
    wentRight: Mapped[list[str]] = mapped_column("went_right", JSONB, nullable=False, default=list)
    wentWrong: Mapped[list[str]] = mapped_column("went_wrong", JSONB, nullable=False, default=list)
    lessons: Mapped[list[str]] = mapped_column("lessons", JSONB, nullable=False, default=list)
    details: Mapped[dict[str, Any]] = mapped_column("details", JSONB, nullable=False, default=dict)
    # what this trade changed: scorecard status before / after, guards proposed or applied
    learning: Mapped[dict[str, Any]] = mapped_column("learning", JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("uq_trade_autopsies_trade", "trade_id", unique=True, postgresql_where=text("status = 1")),
    )
