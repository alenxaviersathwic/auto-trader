"""Suggestion masters (one row per card per Start) + one trade_suggestions table

Replaces the server-side loop (suggestion_runs) and the 12 per-underlying tables
(nifty_suggestions, gold_suggestions, ...). The old tables are left in place, read-only,
so history is not lost; nothing writes to them any more.

Revision ID: 0010_suggestion_masters
Revises: 0009_strategy_active_days
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0010_suggestion_masters"
down_revision: Union[str, None] = "0009_strategy_active_days"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1"),
    ]


def upgrade() -> None:
    op.create_table(
        "suggestion_masters",
        *_base(),
        sa.Column("trade_date", sa.String(10), nullable=False),
        sa.Column("session_no", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("underlying_code", sa.String(30), nullable=False),
        sa.Column("underlying_type", sa.String(10), nullable=False),
        sa.Column("state", sa.String(12), nullable=False, server_default="RUNNING"),
        sa.Column("stop_reason", sa.String(40), nullable=True),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("research_run_id", sa.BigInteger(), nullable=True),
        sa.Column("research_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("direction", sa.String(10), nullable=True),
        sa.Column("news_status", sa.String(20), nullable=True),
        sa.Column("in_research", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("iterations_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("iterations_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suggestions_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_suggestion_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("top_confidence", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("last_note", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_suggestion_masters_day_code", "suggestion_masters", ["trade_date", "underlying_code"])
    op.create_index(
        "uq_suggestion_masters_day_code_session", "suggestion_masters",
        ["trade_date", "underlying_code", "session_no"], unique=True, postgresql_where=sa.text("status = 1"),
    )
    op.create_index("ix_suggestion_masters_state", "suggestion_masters", ["state"])

    op.create_table(
        "trade_suggestions",
        *_base(),
        sa.Column("master_id", sa.BigInteger(), sa.ForeignKey("suggestion_masters.id"), nullable=False),
        sa.Column("iteration_no", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(48), nullable=False),
        sa.Column("underlying_code", sa.String(30), nullable=False),
        sa.Column("underlying_type", sa.String(10), nullable=False),
        sa.Column("contract_id", sa.String(60), nullable=False),
        sa.Column("instrument_key", sa.String(80), nullable=True),
        sa.Column("option_type", sa.String(2), nullable=False),
        sa.Column("spot", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("strike", sa.Numeric(12, 2), nullable=False),
        sa.Column("expiry", sa.String(10), nullable=False),
        sa.Column("entry", sa.Numeric(12, 2), nullable=False),
        sa.Column("stop", sa.Numeric(12, 2), nullable=False),
        sa.Column("target", sa.Numeric(12, 2), nullable=False),
        sa.Column("profit_margin_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("reward_risk", sa.Numeric(6, 2), nullable=False),
        sa.Column("confidence", sa.SmallInteger(), nullable=False),
        sa.Column("risk_level", sa.String(8), nullable=False, server_default="MEDIUM"),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("strategy", sa.String(100), nullable=True),
        sa.Column("reasons", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("risks", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("source", sa.String(10), nullable=False, server_default="AI"),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(12), nullable=False, server_default="PENDING"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_trade_suggestions_master_id", "trade_suggestions", ["master_id"])
    op.create_index("ix_trade_suggestions_code_latest", "trade_suggestions", ["underlying_code", "is_latest"])
    op.create_index("ix_trade_suggestions_outcome", "trade_suggestions", ["outcome"])

    # suggestion_memories.suggestion_id now points at trade_suggestions.id. Old PENDING memories point at
    # ids in the retired per-underlying tables and could collide with new ids, so close them out.
    op.execute("UPDATE suggestion_memories SET outcome = 'EXPIRED' WHERE outcome = 'PENDING'")


def downgrade() -> None:
    op.drop_table("trade_suggestions")
    op.drop_table("suggestion_masters")
