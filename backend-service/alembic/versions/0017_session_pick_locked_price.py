"""Locked price on session picks + fast index for the session loop's fresh-opportunity read

Revision ID: 0017_session_pick_locked_price
Revises: 0016_session_picks
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0017_session_pick_locked_price"
down_revision: Union[str, None] = "0016_session_picks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("session_picks", sa.Column("locked_price", sa.Numeric(12, 2), nullable=True))
    # the session loop reads "latest, PENDING rows created in the last 30 seconds" every second
    op.create_index(
        "ix_trade_opportunities_loop_fresh", "trade_opportunities", ["created_at"],
        postgresql_where=sa.text("is_latest AND outcome = 'PENDING' AND status = 1"),
    )


def downgrade() -> None:
    op.drop_index("ix_trade_opportunities_loop_fresh", table_name="trade_opportunities")
    op.drop_column("session_picks", "locked_price")
