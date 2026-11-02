"""Rename suggestion tables and columns to opportunities

Revision ID: 0011_rename_to_opportunities
Revises: 0010_suggestion_masters
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0011_rename_to_opportunities"
down_revision: Union[str, None] = "0010_suggestion_masters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS alembic_version ALTER COLUMN version_num TYPE VARCHAR(64);")
    # 1. suggestion_runs -> opportunity_runs
    op.execute("ALTER TABLE IF EXISTS suggestion_runs RENAME TO opportunity_runs;")

    # 2. suggestion_masters -> opportunity_masters
    op.execute("ALTER TABLE IF EXISTS suggestion_masters RENAME TO opportunity_masters;")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'opportunity_masters' AND column_name = 'suggestions_total'
            ) THEN
                ALTER TABLE opportunity_masters RENAME COLUMN suggestions_total TO opportunities_total;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'opportunity_masters' AND column_name = 'last_suggestion_count'
            ) THEN
                ALTER TABLE opportunity_masters RENAME COLUMN last_suggestion_count TO last_opportunity_count;
            END IF;
        END $$;
    """)
    op.execute("ALTER INDEX IF EXISTS ix_suggestion_masters_day_code RENAME TO ix_opportunity_masters_day_code;")
    op.execute(
        "ALTER INDEX IF EXISTS uq_suggestion_masters_day_code_session "
        "RENAME TO uq_opportunity_masters_day_code_session;"
    )
    op.execute("ALTER INDEX IF EXISTS ix_suggestion_masters_state RENAME TO ix_opportunity_masters_state;")

    # 3. trade_suggestions -> trade_opportunities
    op.execute("ALTER TABLE IF EXISTS trade_suggestions RENAME TO trade_opportunities;")
    op.execute("ALTER INDEX IF EXISTS ix_trade_suggestions_master_id RENAME TO ix_trade_opportunities_master_id;")
    op.execute("ALTER INDEX IF EXISTS ix_trade_suggestions_code_latest RENAME TO ix_trade_opportunities_code_latest;")
    op.execute("ALTER INDEX IF EXISTS ix_trade_suggestions_outcome RENAME TO ix_trade_opportunities_outcome;")

    # 4. suggestion_memories -> opportunity_memories
    op.execute("ALTER TABLE IF EXISTS suggestion_memories RENAME TO opportunity_memories;")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'opportunity_memories' AND column_name = 'suggestion_id'
            ) THEN
                ALTER TABLE opportunity_memories RENAME COLUMN suggestion_id TO opportunity_id;
            END IF;
        END $$;
    """)
    op.execute(
        "ALTER INDEX IF EXISTS ix_suggestion_memories_underlying "
        "RENAME TO ix_opportunity_memories_underlying;"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX IF EXISTS ix_opportunity_memories_underlying "
        "RENAME TO ix_suggestion_memories_underlying;"
    )
    op.execute(
        "ALTER TABLE IF EXISTS opportunity_memories "
        "RENAME COLUMN opportunity_id TO suggestion_id;"
    )
    op.execute("ALTER TABLE IF EXISTS opportunity_memories RENAME TO suggestion_memories;")

    op.execute("ALTER INDEX IF EXISTS ix_trade_opportunities_outcome RENAME TO ix_trade_suggestions_outcome;")
    op.execute("ALTER INDEX IF EXISTS ix_trade_opportunities_code_latest RENAME TO ix_trade_suggestions_code_latest;")
    op.execute("ALTER INDEX IF EXISTS ix_trade_opportunities_master_id RENAME TO ix_trade_suggestions_master_id;")
    op.execute("ALTER TABLE IF EXISTS trade_opportunities RENAME TO trade_suggestions;")

    op.execute("ALTER INDEX IF EXISTS ix_opportunity_masters_state RENAME TO ix_suggestion_masters_state;")
    op.execute(
        "ALTER INDEX IF EXISTS uq_opportunity_masters_day_code_session "
        "RENAME TO uq_suggestion_masters_day_code_session;"
    )
    op.execute("ALTER INDEX IF EXISTS ix_opportunity_masters_day_code RENAME TO ix_suggestion_masters_day_code;")
    op.execute(
        "ALTER TABLE IF EXISTS opportunity_masters "
        "RENAME COLUMN last_opportunity_count TO last_suggestion_count;"
    )
    op.execute(
        "ALTER TABLE IF EXISTS opportunity_masters "
        "RENAME COLUMN opportunities_total TO suggestions_total;"
    )
    op.execute("ALTER TABLE IF EXISTS opportunity_masters RENAME TO suggestion_masters;")

    op.execute("ALTER TABLE IF EXISTS opportunity_runs RENAME TO suggestion_runs;")

