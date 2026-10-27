"""Create suggestion engine tables

Revision ID: 0006_create_suggestion_tables
Revises: 0005_research_news_blog
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0006_create_suggestion_tables"
down_revision: Union[str, None] = "0005_research_news_blog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1"),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.create_table(
        "suggestion_runs", *_base(),
        sa.Column("loop_id", sa.String(40), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.String(20), nullable=False, server_default="QUEUED"),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("research_run_id", sa.BigInteger(), nullable=True),
        sa.Column("current_node", sa.String(50), nullable=True),
        sa.Column("progress_pct", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("stats", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_table(
        "suggestions", *_base(),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("underlying_code", sa.String(30), nullable=False),
        sa.Column("underlying_type", sa.String(10), nullable=False),
        sa.Column("contract_id", sa.String(60), nullable=False),
        sa.Column("instrument_key", sa.String(80), nullable=True),
        sa.Column("option_type", sa.String(2), nullable=False),
        sa.Column("strike", sa.Numeric(12, 2), nullable=False),
        sa.Column("expiry", sa.String(10), nullable=False),
        sa.Column("entry", sa.Numeric(12, 2), nullable=False),
        sa.Column("stop", sa.Numeric(12, 2), nullable=False),
        sa.Column("target", sa.Numeric(12, 2), nullable=False),
        sa.Column("profit_margin_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("reward_risk", sa.Numeric(6, 2), nullable=False),
        sa.Column("confidence", sa.SmallInteger(), nullable=False),
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
    op.create_index("ix_suggestions_run_id", "suggestions", ["run_id"])
    op.create_table(
        "suggestion_memories", *_base(),
        sa.Column("suggestion_id", sa.BigInteger(), nullable=True),
        sa.Column("underlying_code", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("day_type", sa.String(20), nullable=True),
        sa.Column("hour_bucket", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(12), nullable=False, server_default="PENDING"),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("brief_hash", sa.String(64), nullable=True),
        sa.Column("last_ai_answer", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_suggestion_memories_underlying", "suggestion_memories", ["underlying_code"])


def downgrade() -> None:
    op.drop_table("suggestion_memories")
    op.drop_table("suggestions")
    op.drop_table("suggestion_runs")
