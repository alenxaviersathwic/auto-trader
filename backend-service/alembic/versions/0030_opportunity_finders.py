"""Opportunity finders as an entity (optionTypes per finder) and the finders a session uses

- opportunity_finders: one row per finder, same shape for all; option_types = markets it works on (INDEX / COMMODITY).
  Seeded with the three finders. Values are frozen here (not imported) so the migration never changes later.
- trading_sessions.finders: the finders that feed a session. `traders` keeps the session MANAGER (one code).
  Back-fill: old sessions get finders = traders (what they used before); old Commodity Desk sessions get the
  Indian Quant Desk as manager (there is no commodity manager any more) and the desk as their finder.

Revision ID: 0030_opportunity_finders
Revises: 0029_commodity_desk
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_opportunity_finders"
down_revision: Union[str, None] = "0029_commodity_desk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FINDERS = [
    {
        "code": "FLOW_MOMENTUM_TRADER", "name": "Flow & Momentum Trader", "short_label": "FLOW + MOMENTUM",
        "badge_color": "green", "option_types": ["INDEX"], "sort_order": 1, "live_only": False,
        "methodology": "Noise-area breakouts and institutional flow, held with an R-multiple trail (no fixed target)",
        "entry_logic": "Takes the engine's breakout and flow setups: noise breakout, FII open drive, late-day "
                       "momentum, plus VWAP pullback / range breakout / gap-and-go inside an active breakout on the same side.",
        "trail_logic": "Momentum setups: stop to breakeven at +1.5R, then trail 2R under the peak, no fixed target. Other "
                       "entries: step guard (+30% of the move locked at 50% progress, +50% at 80%).",
        "strategies": ["NOISE_BREAKOUT", "FII_OPEN_DRIVE", "LATE_DAY_MOMENTUM", "VWAP_PULLBACK",
                       "RANGE_BREAKOUT", "GAP_GO"],
        "checks": ["Noise-area breakout, FII open drive, late-day momentum",
                   "VWAP pullback / range breakout only inside an active breakout",
                   "Day type, dealer gamma and 1-minute timing agree"],
        "drivers": "Mostly national: FII index-futures positioning, NSE dealer gamma, noise area, RBI / domestic news",
    },
    {
        "code": "FIB_GOLDEN_TRADER", "name": "Fib Golden-Pocket Trader", "short_label": "FIB + OI + VOL",
        "badge_color": "cyan", "option_types": ["INDEX"], "sort_order": 2, "live_only": False,
        "methodology": "0.50-0.618 pullback of an impulse swing, confirmed by option-chain OI and futures volume",
        "entry_logic": "Finds an impulse swing of at least 3 ATR on the 5-minute chart, waits for the pullback into the "
                       "0.50-0.618 pocket and a 5-minute close turning back with the swing. Enters only when the option "
                       "chain and volume confirm.",
        "trail_logic": "Stop behind the 0.786 retracement. Locks half the profit at 80% of the move, then steps the "
                       "target to the 1.272 and 1.618 extensions while momentum holds.",
        "strategies": ["FIB_GOLDEN_POCKET"],
        "checks": ["Pullback into the 0.50-0.618 pocket of a 3 ATR swing",
                   "Price action: a corrective pullback, then a pin bar, engulfing or inside-bar break at the pocket",
                   "Option-chain OI: wall behind the stop, none blocking the target",
                   "Volume: quiet pullback, active turn bar"],
        "drivers": "Mostly national: NSE option chain OI, futures volume, FII flow, domestic news",
    },
    {
        "code": "COMMODITY_DESK_TRADER", "name": "Commodity Desk", "short_label": "DESK + AGENTS",
        "badge_color": "amber", "option_types": ["COMMODITY"], "sort_order": 3, "live_only": True,
        "methodology": "MCX desk: clock, structure, option-chain and news sub-agents report; an LLM head trader decides",
        "entry_logic": "Sub-agents read the MCX session clock, the 1/5/15-minute futures structure, the live option chain "
                       "and the news. They propose trend pullbacks, fresh range breakouts and Fib pockets; a code risk "
                       "gate refuses unsafe ones; the head trader takes one setup or waits.",
        "trail_logic": "Momentum management: stop to breakeven at +1.5R, then trail 2R under the peak.",
        "strategies": ["DESK_TREND_PULLBACK", "DESK_RANGE_BREAK", "DESK_FIB_POCKET"],
        "checks": ["Session clock: MCX phase (Asia / Europe / US open), EIA and US data releases",
                   "Price structure on 1, 5 and 15-minute futures: trend pullback, fresh range break, Fib pocket",
                   "Option chain of the traded expiry: PCR, OI walls, ATM liquidity",
                   "News: Research Engine read and sudden-move explanations",
                   "Code risk gate, then an LLM head trader writes its reasoning and takes one setup or waits"],
        "drivers": "International: US / London session hours, EIA and US data, dollar, global news",
    },
]


def upgrade() -> None:
    t = op.create_table(
        "opportunity_finders",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("short_label", sa.String(40), nullable=False, server_default=""),
        sa.Column("badge_color", sa.String(20), nullable=False, server_default="slate"),
        sa.Column("option_types", postgresql.JSONB(), nullable=False, server_default=sa.text("'[\"INDEX\"]'::jsonb")),
        sa.Column("methodology", sa.Text(), nullable=False, server_default=""),
        sa.Column("entry_logic", sa.Text(), nullable=False, server_default=""),
        sa.Column("trail_logic", sa.Text(), nullable=False, server_default=""),
        sa.Column("strategies", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("checks", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("drivers", sa.Text(), nullable=False, server_default=""),
        sa.Column("live_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("extra", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("uq_opportunity_finders_code_active", "opportunity_finders", ["code"], unique=True,
                    postgresql_where=sa.text("status = 1"))
    op.bulk_insert(t, [dict(f) for f in FINDERS])

    op.add_column("trading_sessions", sa.Column("finders", postgresql.JSONB(), nullable=False,
                                                server_default=sa.text("'[]'::jsonb")))
    # old sessions: they used exactly the finders named in `traders`
    op.execute("UPDATE trading_sessions SET finders = traders")
    # no commodity manager any more: desk sessions keep the desk as finder, Indian Quant Desk as manager
    op.execute("UPDATE trading_sessions SET traders = '[\"FLOW_MOMENTUM_TRADER\"]'::jsonb "
               "WHERE traders @> '[\"COMMODITY_DESK_TRADER\"]'::jsonb")


def downgrade() -> None:
    op.execute("UPDATE trading_sessions SET traders = finders "
               "WHERE finders @> '[\"COMMODITY_DESK_TRADER\"]'::jsonb")
    op.drop_column("trading_sessions", "finders")
    op.drop_index("uq_opportunity_finders_code_active", table_name="opportunity_finders")
    op.drop_table("opportunity_finders")
