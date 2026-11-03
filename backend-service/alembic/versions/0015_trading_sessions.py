"""Create trading_sessions table (capital/risk/scope/automation envelope for execution)

Revision ID: 0015_trading_sessions
Revises: 0014_strategy_stop_loss_pct
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0015_trading_sessions"
down_revision: Union[str, None] = "0014_strategy_stop_loss_pct"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trading_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("trade_date", sa.String(10), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("capital", sa.Numeric(14, 2), nullable=False),
        sa.Column("max_loss_percentage", sa.Numeric(5, 2), nullable=False, server_default="3.00"),
        sa.Column("scope", sa.String(10), nullable=False),
        sa.Column("underlyings", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("commodity_items", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("session_type", sa.String(12), nullable=False, server_default="MANUAL"),
        sa.Column("route_through_upstox", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("session_status", sa.String(10), nullable=False, server_default="ACTIVE"),
        sa.Column("halt_reason", sa.String(40), nullable=True),
        sa.Column("halted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_trading_sessions_trade_date", "trading_sessions", ["trade_date"])
    op.create_index("ix_trading_sessions_user_id", "trading_sessions", ["user_id"])
    op.create_index("ix_trading_sessions_session_status", "trading_sessions", ["session_status"])


def downgrade() -> None:
    op.drop_index("ix_trading_sessions_session_status", table_name="trading_sessions")
    op.drop_index("ix_trading_sessions_user_id", table_name="trading_sessions")
    op.drop_index("ix_trading_sessions_trade_date", table_name="trading_sessions")
    op.drop_table("trading_sessions")
