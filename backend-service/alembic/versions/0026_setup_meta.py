"""setup_meta: what a setup found on the chart, carried from the opportunity to the pick and the trade

Nullable JSONB on trade_opportunities, session_picks and session_picks_archive (the archive job copies every
session_picks column by name, so both pick tables need it). Today only the Fib golden pocket fills it
(opportunities/service/fib_pocket.py setup_meta()): the real swing and its Fibonacci levels.

Revision ID: 0026_setup_meta
Revises: 0025_two_traders_risk_level
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026_setup_meta"
down_revision: Union[str, None] = "0025_two_traders_risk_level"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("trade_opportunities", "session_picks", "session_picks_archive")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("setup_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "setup_meta")
