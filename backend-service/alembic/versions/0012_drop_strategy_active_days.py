"""Drop active_days and day_overrides from strategies (replaced by tag-based day-context matching)

Revision ID: 0012_drop_strategy_active_days
Revises: 0011_rename_to_opportunities
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0012_drop_strategy_active_days"
down_revision: Union[str, None] = "0011_rename_to_opportunities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The weekly MON..SUN schedule + per-date override concept is retired: a strategy's own `tags`
    # field (AFTER_HOLIDAY, DAY_MONDAY, EXPIRY_DAY, ...) matched against the day's computed context
    # tags (app.modules.opportunities.service.day_context) is now how "is this strategy suited to
    # today" is expressed -- it nudges opportunity confidence instead of hard-gating eligibility.
    op.execute("ALTER TABLE strategies DROP COLUMN IF EXISTS active_days;")
    op.execute("ALTER TABLE strategies DROP COLUMN IF EXISTS day_overrides;")


def downgrade() -> None:
    op.execute("ALTER TABLE strategies ADD COLUMN IF NOT EXISTS active_days JSONB NOT NULL DEFAULT '[]'::jsonb;")
    op.execute("ALTER TABLE strategies ADD COLUMN IF NOT EXISTS day_overrides JSONB NOT NULL DEFAULT '[]'::jsonb;")
