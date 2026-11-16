"""learning module (autopsy agent, setup scorecards, setup guards) + batch analysis on session picks

Revision ID: 0027_learning_and_batches
Revises: 0026_setup_meta
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027_learning_and_batches"
down_revision: Union[str, None] = "0026_setup_meta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1"),
    ]


def upgrade() -> None:
    op.create_table(
        "trade_autopsies", *_base(),
        sa.Column("trade_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("setup", sa.String(100), nullable=False),
        sa.Column("trader_code", sa.String(40), nullable=True),
        sa.Column("underlying_code", sa.String(30), nullable=False),
        sa.Column("option_type", sa.String(2), nullable=False),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("verdict", sa.String(24), nullable=False),
        sa.Column("r_multiple", sa.Numeric(8, 2), nullable=False),
        sa.Column("mfe_r", sa.Numeric(8, 2), nullable=False),
        sa.Column("mae_r", sa.Numeric(8, 2), nullable=False),
        sa.Column("giveback_pct", sa.Numeric(8, 1), nullable=True),
        sa.Column("net_pnl", sa.Numeric(14, 2), nullable=False),
        sa.Column("planned_target_pct", sa.Numeric(8, 2), nullable=True),
        sa.Column("tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("went_right", JSONB, nullable=False, server_default="[]"),
        sa.Column("went_wrong", JSONB, nullable=False, server_default="[]"),
        sa.Column("lessons", JSONB, nullable=False, server_default="[]"),
        sa.Column("details", JSONB, nullable=False, server_default="{}"),
        sa.Column("learning", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("ix_trade_autopsies_session_id", "trade_autopsies", ["session_id"])
    op.create_index("ix_trade_autopsies_setup", "trade_autopsies", ["setup"])
    op.create_index("uq_trade_autopsies_trade", "trade_autopsies", ["trade_id"], unique=True,
                    postgresql_where=sa.text("status = 1"))

    op.create_table(
        "setup_scorecards", *_base(),
        sa.Column("setup", sa.String(100), nullable=False),
        sa.Column("policy", sa.String(24), nullable=True),
        sa.Column("closed_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("net_pnl", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("avg_r", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("win_rate_pct", sa.Numeric(6, 1), nullable=False, server_default="0"),
        sa.Column("expectancy", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("score_status", sa.String(10), nullable=False, server_default="ACTIVE"),
        sa.Column("status_reason", sa.String(300), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_trade_id", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("uq_setup_scorecards_setup", "setup_scorecards", ["setup"], unique=True,
                    postgresql_where=sa.text("status = 1"))

    op.create_table(
        "setup_guards", *_base(),
        sa.Column("setup", sa.String(100), nullable=False),
        sa.Column("guard_type", sa.String(24), nullable=False),
        sa.Column("tag", sa.String(24), nullable=False),
        sa.Column("params", JSONB, nullable=False, server_default="{}"),
        sa.Column("text", sa.String(300), nullable=False),
        sa.Column("evidence", JSONB, nullable=False, server_default="{}"),
        sa.Column("guard_state", sa.String(10), nullable=False, server_default="PROPOSED"),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rule_id", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_setup_guards_setup", "setup_guards", ["setup"])

    for table in ("session_picks", "session_picks_archive"):
        op.add_column(table, sa.Column("outcome_analysis", JSONB, nullable=True))


def downgrade() -> None:
    for table in ("session_picks", "session_picks_archive"):
        op.drop_column(table, "outcome_analysis")
    op.drop_table("setup_guards")
    op.drop_table("setup_scorecards")
    op.drop_table("trade_autopsies")
