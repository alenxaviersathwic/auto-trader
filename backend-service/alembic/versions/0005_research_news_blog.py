"""Add latest_news, affect_news, neutral_news, and blog_summary to research_candidates

Revision ID: 0005_add_research_news_and_blog_summary
Revises: 0004_create_research_tables
Create Date: 2026-10-26 16:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_research_news_blog"
down_revision: Union[str, None] = "0004_create_research_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE research_candidates
        ADD COLUMN IF NOT EXISTS latest_news JSONB NOT NULL DEFAULT '[]'::jsonb,
        ADD COLUMN IF NOT EXISTS affect_news JSONB NOT NULL DEFAULT '[]'::jsonb,
        ADD COLUMN IF NOT EXISTS neutral_news JSONB NOT NULL DEFAULT '[]'::jsonb,
        ADD COLUMN IF NOT EXISTS blog_summary TEXT;
        """
    )


def downgrade() -> None:
    op.drop_column("research_candidates", "blog_summary")
    op.drop_column("research_candidates", "neutral_news")
    op.drop_column("research_candidates", "affect_news")
    op.drop_column("research_candidates", "latest_news")
