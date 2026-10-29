"""Add active_days and day_overrides to strategies

Revision ID: 0009_strategy_active_days
Revises: 0008_per_underlying_suggestions
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0009_strategy_active_days"
down_revision: Union[str, None] = "0008_per_underlying_suggestions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # active_days: weekday codes (MON..SUN). Empty array = runs every trading day.
    op.execute("ALTER TABLE strategies ADD COLUMN IF NOT EXISTS active_days JSONB NOT NULL DEFAULT '[]'::jsonb;")
    # day_overrides: [{date: 'YYYY-MM-DD', active: bool, reason: str|null}] — date-specific exceptions
    # (holiday shifts, special sessions). An override always wins over active_days.
    op.execute("ALTER TABLE strategies ADD COLUMN IF NOT EXISTS day_overrides JSONB NOT NULL DEFAULT '[]'::jsonb;")


def downgrade() -> None:
    op.drop_column("strategies", "day_overrides")
    op.drop_column("strategies", "active_days")
