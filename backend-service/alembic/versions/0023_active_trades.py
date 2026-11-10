"""active_trades: independent trader loop positions per locked pick

Revision ID: 0023_active_trades
Revises: 0022_trade_opportunities_realized_pnl
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_active_trades"
down_revision: Union[str, None] = "0022_trade_opportunities_realized_pnl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "active_trades",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("pick_id", sa.BigInteger(), nullable=False),
        sa.Column("opportunity_id", sa.BigInteger(), nullable=False),
        sa.Column("opportunity_ref", sa.String(48), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("underlying_code", sa.String(30), nullable=False),
        sa.Column("option_type", sa.String(2), nullable=False),
        sa.Column("strike", sa.Numeric(12, 2), nullable=False),
        sa.Column("expiry", sa.String(10), nullable=False),
        sa.Column("instrument_key", sa.String(80), nullable=True),
        sa.Column("strategy", sa.String(100), nullable=True),
        sa.Column("confidence", sa.SmallInteger(), nullable=False),
        sa.Column("win_rate_pct", sa.Numeric(6, 2), nullable=False, server_default="50.00"),
        sa.Column("trader_profile", sa.String(24), nullable=False, server_default="'STEP_GUARD'"),
        sa.Column("session_type", sa.String(12), nullable=False, server_default="'MANUAL'"),
        sa.Column("route_through_upstox", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("lots", sa.Integer(), nullable=False),
        sa.Column("lot_units", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("planned_entry", sa.Numeric(12, 2), nullable=False),
        sa.Column("entry_at", sa.Numeric(12, 2), nullable=False),
        sa.Column("capital_used", sa.Numeric(14, 2), nullable=False),
        sa.Column("initial_stop", sa.Numeric(12, 2), nullable=False),
        sa.Column("initial_target", sa.Numeric(12, 2), nullable=False),
        sa.Column("current_stop", sa.Numeric(12, 2), nullable=False),
        sa.Column("current_target", sa.Numeric(12, 2), nullable=False),
        sa.Column("last_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("peak_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("trough_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("entry_order_id", sa.String(80), nullable=True),
        sa.Column("exit_order_id", sa.String(80), nullable=True),
        sa.Column("broker_status", sa.String(20), nullable=False, server_default="'SIMULATED'"),
        sa.Column("broker_error", sa.String(500), nullable=True),
        sa.Column("trade_state", sa.String(16), nullable=False, server_default="'RUNNING'"),
        sa.Column("exit_reason", sa.String(32), nullable=True),
        sa.Column("exit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("gross_pnl", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("charges", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("net_pnl", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("pnl_pct", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hold_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trail_events", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("market_telemetry", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_active_trades_session_id", "active_trades", ["session_id"])
    op.create_index("ix_active_trades_session_state", "active_trades", ["session_id", "trade_state"])
    op.create_index(
        "uq_active_trades_pick_id",
        "active_trades",
        ["pick_id"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_active_trades_pick_id", table_name="active_trades")
    op.drop_index("ix_active_trades_session_state", table_name="active_trades")
    op.drop_index("ix_active_trades_session_id", table_name="active_trades")
    op.drop_table("active_trades")
