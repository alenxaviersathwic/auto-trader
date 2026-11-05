"""Session start / close time (IST trading hours of a session)

Revision ID: 0018_session_hours
Revises: 0017_session_pick_locked_price
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0018_session_hours"
down_revision: Union[str, None] = "0017_session_pick_locked_price"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trading_sessions", sa.Column("start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trading_sessions", sa.Column("close_at", sa.DateTime(timezone=True), nullable=True))
    # existing sessions get the standard hours of their trade date (IST): 09:15 - 15:45
    op.execute("UPDATE trading_sessions SET start_at = (trade_date || ' 09:15:00+05:30')::timestamptz")
    op.execute("UPDATE trading_sessions SET close_at = (trade_date || ' 15:45:00+05:30')::timestamptz")
    op.alter_column("trading_sessions", "start_at", nullable=False)
    op.alter_column("trading_sessions", "close_at", nullable=False)


def downgrade() -> None:
    op.drop_column("trading_sessions", "close_at")
    op.drop_column("trading_sessions", "start_at")
