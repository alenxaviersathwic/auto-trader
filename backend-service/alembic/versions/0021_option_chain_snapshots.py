"""option_chain_snapshots: the option chain as the engine saw it, once a minute (for chain-based backtests)

Revision ID: 0021_option_chain_snapshots
Revises: 0020_opportunity_time_machine
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_option_chain_snapshots"
down_revision: Union[str, None] = "0020_opportunity_time_machine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "option_chain_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("underlying_code", sa.String(30), nullable=False),
        sa.Column("expiry", sa.String(10), nullable=False),
        sa.Column("spot", sa.Numeric(14, 2), nullable=False),
        sa.Column("pcr", sa.Numeric(8, 3), nullable=True),
        sa.Column("atm_straddle", sa.Numeric(12, 2), nullable=True),
        sa.Column("vix", sa.Numeric(8, 2), nullable=True),
        sa.Column("strikes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.create_index("ix_option_chain_snapshots_code_time", "option_chain_snapshots", ["underlying_code", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_option_chain_snapshots_code_time", table_name="option_chain_snapshots")
    op.drop_table("option_chain_snapshots")
