"""trade_opportunities.time_machine: the Time Machine odds of each pick at save time

Revision ID: 0020_opportunity_time_machine
Revises: 0019_session_picks_archive
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_opportunity_time_machine"
down_revision: Union[str, None] = "0019_session_picks_archive"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trade_opportunities", sa.Column("time_machine", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("trade_opportunities", "time_machine")
