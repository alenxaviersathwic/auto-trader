"""trading_sessions: add traders JSONB list for specialist trader selection per session

Revision ID: 0024_session_traders
Revises: 0023_active_trades
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_session_traders"
down_revision: Union[str, None] = "0023_active_trades"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trading_sessions",
        sa.Column(
            "traders",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='["FIB_GOLDEN_TRADER", "ORB_WAVE_TRADER", "FLOW_VWAP_TRADER"]',
        ),
    )


def downgrade() -> None:
    op.drop_column("trading_sessions", "traders")

