"""trade_opportunities: persist the realized exit price / rupee P&L on resolution

10 Nov 2026 research review: the per-trade exit was computed in memory (run_service._evaluate_opportunities)
but never saved, so neither a real daily rupee-drawdown guardrail nor a per-setup rolling-expectancy
demotion check (Freqtrade's MaxDrawdown / LowProfitPairs analogues) had real numbers to work from.

Revision ID: 0022_trade_opportunities_realized_pnl
Revises: 0021_option_chain_snapshots
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_trade_opportunities_realized_pnl"
down_revision: Union[str, None] = "0021_option_chain_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trade_opportunities", sa.Column("exit_price", sa.Numeric(12, 2), nullable=True))
    # Rupee P&L for ONE lot (exit_price - entry) * lot_size; the engine is long-only (always buys the option),
    # so no CE/PE sign flip is needed -- a lower exit price is a loss regardless of side.
    op.add_column("trade_opportunities", sa.Column("realized_pnl", sa.Numeric(14, 2), nullable=True))
    # Supports guardrails._demoted_setups()'s per-(setup, side) lookback query: resolved rows for one
    # underlying, newest first, filtered by strategy name.
    op.create_index(
        "ix_trade_opportunities_underlying_strategy_resolved",
        "trade_opportunities",
        ["underlying_code", "strategy", "resolved_at"],
        postgresql_where=sa.text("outcome != 'PENDING' AND status = 1"),
    )


def downgrade() -> None:
    op.drop_index("ix_trade_opportunities_underlying_strategy_resolved", table_name="trade_opportunities")
    op.drop_column("trade_opportunities", "realized_pnl")
    op.drop_column("trade_opportunities", "exit_price")
