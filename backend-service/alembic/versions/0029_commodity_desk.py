"""Commodity Desk: every desk decision (sub-agent reports + head trader reasoning) and sudden market moves with the
news found for them

Revision ID: 0029_commodity_desk
Revises: 0028_autopsy_per_manager
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029_commodity_desk"
down_revision: Union[str, None] = "0028_autopsy_per_manager"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1"),
    ]


def upgrade() -> None:
    op.create_table(
        "commodity_desk_decisions", *_base(),
        sa.Column("underlying_code", sa.String(30), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("phase", sa.String(12), nullable=False),
        sa.Column("spot", sa.Float(), nullable=True),
        sa.Column("decision", sa.String(8), nullable=False),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("setup_name", sa.String(40), nullable=True),
        sa.Column("side", sa.String(2), nullable=True),
        sa.Column("conviction", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("thinking", sa.Text(), nullable=False, server_default=""),
        sa.Column("watch_for", sa.String(300), nullable=False, server_default=""),
        sa.Column("agents", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("candidates", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("chosen", postgresql.JSONB(), nullable=True),
        sa.Column("outcome", sa.String(200), nullable=True),
    )
    op.create_index("ix_commodity_desk_decisions_underlying_code", "commodity_desk_decisions", ["underlying_code"])
    op.create_index("ix_commodity_desk_decisions_decided_at", "commodity_desk_decisions", ["decided_at"])
    op.create_table(
        "market_moves", *_base(),
        sa.Column("underlying_code", sa.String(30), nullable=False),
        sa.Column("underlying_type", sa.String(10), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(4), nullable=False),
        sa.Column("window_min", sa.Integer(), nullable=False),
        sa.Column("price_from", sa.Float(), nullable=False),
        sa.Column("price_to", sa.Float(), nullable=False),
        sa.Column("move_pct", sa.Float(), nullable=False),
        sa.Column("move_atr", sa.Float(), nullable=False),
        sa.Column("news_state", sa.String(12), nullable=False),
        sa.Column("cause", sa.String(20), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("headlines", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source", sa.String(8), nullable=True),
    )
    op.create_index("ix_market_moves_underlying_code", "market_moves", ["underlying_code"])
    op.create_index("ix_market_moves_detected_at", "market_moves", ["detected_at"])


def downgrade() -> None:
    op.drop_table("market_moves")
    op.drop_table("commodity_desk_decisions")
