"""One suggestion table per underlying (nifty_suggestions, sensex_suggestions, ...)

Revision ID: 0008_per_underlying_suggestions
Revises: 0007_research_opportunity_score
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0008_per_underlying_suggestions"
down_revision: Union[str, None] = "0007_research_opportunity_score"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CODES = [
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "BANKEX",
    "CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER", "ZINC",
]


def _columns():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("ref", sa.String(40), nullable=False),
        sa.Column("underlying_code", sa.String(30), nullable=False),
        sa.Column("underlying_type", sa.String(10), nullable=False),
        sa.Column("contract_id", sa.String(60), nullable=False),
        sa.Column("instrument_key", sa.String(80), nullable=True),
        sa.Column("option_type", sa.String(2), nullable=False),
        sa.Column("spot", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("strike", sa.Numeric(12, 2), nullable=False),
        sa.Column("expiry", sa.String(10), nullable=False),
        sa.Column("entry", sa.Numeric(12, 2), nullable=False),
        sa.Column("stop", sa.Numeric(12, 2), nullable=False),
        sa.Column("target", sa.Numeric(12, 2), nullable=False),
        sa.Column("profit_margin_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("reward_risk", sa.Numeric(6, 2), nullable=False),
        sa.Column("confidence", sa.SmallInteger(), nullable=False),
        sa.Column("risk_level", sa.String(8), nullable=False, server_default="MEDIUM"),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("strategy", sa.String(100), nullable=True),
        sa.Column("reasons", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("risks", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("source", sa.String(10), nullable=False, server_default="AI"),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(12), nullable=False, server_default="PENDING"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.true()),
    ]


def upgrade() -> None:
    for code in CODES:
        t = f"{code.lower()}_suggestions"
        op.create_table(t, *_columns())
        op.create_index(f"ix_{t}_run_id", t, ["run_id"])
        # carry over anything already saved in the old shared table
        op.execute(
            f"""
            INSERT INTO {t} (created_at, status, run_id, ref, underlying_code, underlying_type, contract_id,
                instrument_key, option_type, spot, strike, expiry, entry, stop, target, profit_margin_pct,
                reward_risk, confidence, risk_level, rank, strategy, reasons, risks, source, valid_until,
                outcome, resolved_at, is_latest)
            SELECT created_at, status, run_id,
                'SG-' || underlying_code || '-' || to_char(created_at, 'YYYYMMDD') || '-' ||
                    lpad(run_id::text, 4, '0') || '-' || lpad(rank::text, 2, '0'),
                underlying_code, underlying_type, contract_id, instrument_key, option_type, 0, strike, expiry,
                entry, stop, target, profit_margin_pct, reward_risk, confidence, 'MEDIUM', rank, strategy,
                reasons, risks, source, valid_until, outcome, resolved_at, is_latest
            FROM suggestions WHERE underlying_code = '{code}';
            """
        )
    op.drop_table("suggestions")


def downgrade() -> None:
    raise NotImplementedError("Per-underlying suggestion tables cannot be merged back automatically")
