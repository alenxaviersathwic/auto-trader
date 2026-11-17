from typing import Any

from sqlalchemy import Boolean, Index, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base_entity import BaseEntity

OPTION_TYPE_VALUES = ("INDEX", "COMMODITY")


class OpportunityFinder(BaseEntity):
    """
    One opportunity finder (a "trader" in the UI). Every finder has the same shape and the same abilities -- it
    reads the scans, thinks, proposes setups and manages the trade it owns -- and differs only in its strategy and
    method. `optionTypes` says which markets it works on: INDEX finders read mostly national drivers (FII flow, NSE
    option chain, RBI / domestic news), COMMODITY finders international ones (US / London hours, EIA, dollar, global
    news). A session is offered only the finders whose optionTypes include its scope, and the engine runs a finder
    only on underlyings of those types.

    The setup logic itself lives in code (opportunity_finder/service, commodity_desk); this row is the finder's
    editable profile. Rows are seeded by migration 0030 from trade_history/service/trader_presets.py.
    """

    __tablename__ = "opportunity_finders"
    __table_args__ = (
        Index("uq_opportunity_finders_code_active", "code", unique=True, postgresql_where=text("status = 1")),
    )

    code: Mapped[str] = mapped_column("code", String(40), nullable=False)
    name: Mapped[str] = mapped_column("name", String(100), nullable=False)
    shortLabel: Mapped[str] = mapped_column("short_label", String(40), nullable=False, default="")
    badgeColor: Mapped[str] = mapped_column("badge_color", String(20), nullable=False, default="slate")
    # which markets this finder works on: any of INDEX | COMMODITY (never empty)
    optionTypes: Mapped[list[str]] = mapped_column("option_types", JSONB, nullable=False, default=lambda: ["INDEX"])
    methodology: Mapped[str] = mapped_column("methodology", Text, nullable=False, default="")
    entryLogic: Mapped[str] = mapped_column("entry_logic", Text, nullable=False, default="")
    trailLogic: Mapped[str] = mapped_column("trail_logic", Text, nullable=False, default="")
    strategies: Mapped[list[str]] = mapped_column("strategies", JSONB, nullable=False, default=list)
    checks: Mapped[list[str]] = mapped_column("checks", JSONB, nullable=False, default=list)
    drivers: Mapped[str] = mapped_column("drivers", Text, nullable=False, default="")  # what moves its market
    liveOnly: Mapped[bool] = mapped_column("live_only", Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column("enabled", Boolean, nullable=False, default=True)
    sortOrder: Mapped[int] = mapped_column("sort_order", SmallInteger, nullable=False, default=0)
    extra: Mapped[dict[str, Any]] = mapped_column("extra", JSONB, nullable=False, default=dict)
