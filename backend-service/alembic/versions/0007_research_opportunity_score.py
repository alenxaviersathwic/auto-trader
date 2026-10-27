"""Add opportunity_score to research_candidates

Revision ID: 0007_research_opportunity_score
Revises: 0006_create_suggestion_tables
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0007_research_opportunity_score"
down_revision: Union[str, None] = "0006_create_suggestion_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE research_candidates ADD COLUMN IF NOT EXISTS opportunity_score NUMERIC(5,1);")
    op.execute("UPDATE research_candidates SET opportunity_score = score WHERE opportunity_score IS NULL;")


def downgrade() -> None:
    op.drop_column("research_candidates", "opportunity_score")
