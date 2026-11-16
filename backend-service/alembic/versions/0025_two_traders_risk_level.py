"""two traders + session risk level

- trading_sessions.risk_level (LOW | MEDIUM | HIGH). Existing rows get HIGH: until now every session accepted
  everything the engine saved, which is what HIGH means. New sessions default to LOW.
- trading_sessions.traders: the three old presets become the two current ones
  (ORB_WAVE_TRADER / FLOW_VWAP_TRADER -> FLOW_MOMENTUM_TRADER).

Revision ID: 0025_two_traders_risk_level
Revises: 0024_session_traders
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_two_traders_risk_level"
down_revision: Union[str, None] = "0024_session_traders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_DEFAULT = '["FIB_GOLDEN_TRADER", "FLOW_MOMENTUM_TRADER"]'
_OLD_DEFAULT = '["FIB_GOLDEN_TRADER", "ORB_WAVE_TRADER", "FLOW_VWAP_TRADER"]'


_LEGACY = {"ORB_WAVE_TRADER": "FLOW_MOMENTUM_TRADER", "FLOW_VWAP_TRADER": "FLOW_MOMENTUM_TRADER"}
_ORDER = ("FIB_GOLDEN_TRADER", "FLOW_MOMENTUM_TRADER")


def _map_traders(codes: list[str]) -> list[str]:
    """Old three-trader codes -> the two current ones, de-duplicated, in preset order (empty = both)."""
    wanted = {_LEGACY.get(c, c) for c in codes}
    return [c for c in _ORDER if c in wanted] or list(_ORDER)


def upgrade() -> None:
    op.add_column(
        "trading_sessions",
        sa.Column("risk_level", sa.String(length=8), nullable=False, server_default="HIGH"),
    )
    op.alter_column("trading_sessions", "risk_level", server_default="LOW")
    bind = op.get_bind()
    for row_id, traders in bind.execute(sa.text("SELECT id, traders FROM trading_sessions")).fetchall():
        current = json.loads(traders) if isinstance(traders, str) else list(traders or [])
        mapped = _map_traders(current)
        if mapped != current:
            bind.execute(
                sa.text("UPDATE trading_sessions SET traders = CAST(:traders AS jsonb) WHERE id = :id"),
                {"traders": json.dumps(mapped), "id": row_id},
            )
    op.alter_column("trading_sessions", "traders", server_default=_NEW_DEFAULT)


def downgrade() -> None:
    op.alter_column("trading_sessions", "traders", server_default=_OLD_DEFAULT)
    op.drop_column("trading_sessions", "risk_level")
