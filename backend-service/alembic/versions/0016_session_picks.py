"""Session picks (the one trade a MANUAL session offers per loop, 20s window) + realized P&L on sessions

Revision ID: 0016_session_picks
Revises: 0015_trading_sessions
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0016_session_picks"
down_revision: Union[str, None] = "0015_trading_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trading_sessions",
        sa.Column("realized_pnl", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.create_table(
        "session_picks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("opportunity_id", sa.BigInteger(), nullable=False),
        sa.Column("opportunity_ref", sa.String(48), nullable=False),
        sa.Column("underlying_code", sa.String(30), nullable=False),
        sa.Column("option_type", sa.String(2), nullable=False),
        sa.Column("strike", sa.Numeric(12, 2), nullable=False),
        sa.Column("expiry", sa.String(10), nullable=False),
        sa.Column("instrument_key", sa.String(80), nullable=True),
        sa.Column("strategy", sa.String(100), nullable=True),
        sa.Column("confidence", sa.SmallInteger(), nullable=False),
        sa.Column("entry", sa.Numeric(12, 2), nullable=False),
        sa.Column("entry_max", sa.Numeric(12, 2), nullable=False),
        sa.Column("stop", sa.Numeric(12, 2), nullable=False),
        sa.Column("target", sa.Numeric(12, 2), nullable=False),
        sa.Column("reward_risk", sa.Numeric(6, 2), nullable=False),
        sa.Column("lots", sa.Integer(), nullable=False),
        sa.Column("lot_units", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("capital_required", sa.Numeric(14, 2), nullable=False),
        sa.Column("risk_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reward_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("expected_net", sa.Numeric(14, 2), nullable=False),
        sa.Column("capital_at_pick", sa.Numeric(14, 2), nullable=False),
        sa.Column("available_at_pick", sa.Numeric(14, 2), nullable=False),
        sa.Column("reasons", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("risks", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("pick_state", sa.String(10), nullable=False, server_default="OFFERED"),
        sa.Column("signal_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hold_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("offered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_session_picks_session_id", "session_picks", ["session_id"])
    op.create_index("ix_session_picks_session_state", "session_picks", ["session_id", "pick_state"])
    # one offer per opportunity per session: a pick the trader let expire is never re-offered
    op.create_index(
        "uq_session_picks_session_opportunity", "session_picks", ["session_id", "opportunity_id"],
        unique=True, postgresql_where=sa.text("status = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_session_picks_session_opportunity", table_name="session_picks")
    op.drop_index("ix_session_picks_session_state", table_name="session_picks")
    op.drop_index("ix_session_picks_session_id", table_name="session_picks")
    op.drop_table("session_picks")
    op.drop_column("trading_sessions", "realized_pnl")
