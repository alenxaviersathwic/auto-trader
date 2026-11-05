"""session_picks_archive: where the daily job moves the picks of finished sessions

Revision ID: 0019_session_picks_archive
Revises: 0018_session_hours
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0019_session_picks_archive"
down_revision: Union[str, None] = "0018_session_hours"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # same columns as session_picks (LIKE), no sequence of its own: ids are copied from the live table
    op.execute("CREATE TABLE session_picks_archive (LIKE session_picks INCLUDING DEFAULTS INCLUDING CONSTRAINTS)")
    op.execute("ALTER TABLE session_picks_archive ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE session_picks_archive ADD COLUMN archived_at timestamptz NOT NULL DEFAULT now()")
    op.execute("ALTER TABLE session_picks_archive ADD PRIMARY KEY (id)")
    op.execute("CREATE INDEX ix_session_picks_archive_session ON session_picks_archive (session_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS session_picks_archive")
