"""Add stop_loss_pct to strategies master table, calibrated from strategy win rate

Revision ID: 0014_strategy_stop_loss_pct
Revises: 0013_opportunity_iterations
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0014_strategy_stop_loss_pct"
down_revision: Union[str, None] = "0013_opportunity_iterations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "strategies",
        sa.Column("stop_loss_pct", sa.Numeric(5, 2), nullable=True),
    )
    # Backfill existing strategies from their newest performance snapshot win_rate_pct, else default 3.50%
    op.execute(
        """
        UPDATE strategies s
        SET stop_loss_pct = COALESCE(
            (
                SELECT ROUND(GREATEST(2.0, LEAST(8.0, 1.5 + (p.win_rate_pct / 100.0) * 6.0))::numeric, 2)
                FROM strategy_performance_snapshots p
                WHERE p.strategy_id = s.id AND p.status = 1
                ORDER BY p.as_of DESC
                LIMIT 1
            ),
            3.50
        )
        WHERE s.stop_loss_pct IS NULL;
        """
    )


def downgrade() -> None:
    op.drop_column("strategies", "stop_loss_pct")

