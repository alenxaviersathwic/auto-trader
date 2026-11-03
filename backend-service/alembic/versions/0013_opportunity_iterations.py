"""Per-iteration (batch) diagnostics: why a batch found nothing, or what it dropped

Revision ID: 0013_opportunity_iterations
Revises: 0012_drop_strategy_active_days
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0013_opportunity_iterations"
down_revision: Union[str, None] = "0012_drop_strategy_active_days"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "opportunity_iterations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("master_id", sa.BigInteger(), nullable=False),
        sa.Column("iteration_no", sa.Integer(), nullable=False),
        sa.Column("underlying_code", sa.String(30), nullable=False),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("saved_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.create_index("ix_opportunity_iterations_master_id", "opportunity_iterations", ["master_id"])
    # Not unique: a failed iteration does not advance iterations_completed, so its number is retried.


def downgrade() -> None:
    op.drop_index("ix_opportunity_iterations_master_id", table_name="opportunity_iterations")
    op.drop_table("opportunity_iterations")
