"""autopsy = each session manager's sub-agent: autopsies, scorecards and guards belong to one session manager

Revision ID: 0028_autopsy_per_manager
Revises: 0027_learning_and_batches
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028_autopsy_per_manager"
down_revision: Union[str, None] = "0027_learning_and_batches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("trade_autopsies", "setup_scorecards", "setup_guards")
# existing rows: the manager is the trader that owns the setup (trade_history/service/trader_presets.py)
OWNER = "CASE WHEN setup = 'FIB_GOLDEN_POCKET' THEN 'FIB_GOLDEN_TRADER' ELSE 'FLOW_MOMENTUM_TRADER' END"


def upgrade() -> None:
    for t in TABLES:
        op.add_column(t, sa.Column("manager_code", sa.String(40), nullable=True))
        op.execute(f"UPDATE {t} SET manager_code = {OWNER}")
        op.alter_column(t, "manager_code", nullable=False)
        op.create_index(f"ix_{t}_manager_code", t, ["manager_code"])
    op.drop_index("uq_setup_scorecards_setup", table_name="setup_scorecards")
    op.create_index("uq_setup_scorecards_manager_setup", "setup_scorecards", ["manager_code", "setup"], unique=True,
                    postgresql_where=sa.text("status = 1"))


def downgrade() -> None:
    op.drop_index("uq_setup_scorecards_manager_setup", table_name="setup_scorecards")
    op.create_index("uq_setup_scorecards_setup", "setup_scorecards", ["setup"], unique=True,
                    postgresql_where=sa.text("status = 1"))
    for t in TABLES:
        op.drop_index(f"ix_{t}_manager_code", table_name=t)
        op.drop_column(t, "manager_code")
