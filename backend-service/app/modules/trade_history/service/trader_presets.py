"""
The opportunity finders ("traders" in the UI) of `auto-trader` (`trader_presets.py`).

Every finder has the same shape and the same abilities (read the scans, think, propose setups, manage the trade it
owns); they differ only in strategy and method, and in `optionTypes` -- the markets they work on. INDEX finders read
mostly national drivers, COMMODITY finders international ones. These presets are the code defaults: migration 0030
seeds the `opportunity_finders` table from them, and that table (opportunity_finder/service/
opportunity_finder_service.py) is what sessions and the engine read, so optionTypes can be changed without a deploy.

A finder is (1) the setups it is allowed to take and (2) how it manages the position once entered.

  FIB_GOLDEN_TRADER     takes ONLY `FIB_GOLDEN_POCKET` (opportunity_finder/service/fib_pocket.py): a pullback into the
                        0.50-0.618 retracement of a real impulse swing, and only when the option chain (OI) and the
                        futures volume both confirm it. Manages the trade along the Fibonacci extensions.
  FLOW_MOMENTUM_TRADER  takes everything else the engine allows (noise breakout, FII open drive, late-day
                        momentum, VWAP / range entries inside an active breakout). Manages the trade with the R-trail
                        momentum exit (menu_builder.MOMO_EXIT) or the step guard.

Until 16 Nov 2026 there were three presets (FIB_GOLDEN / ORB_WAVE / FLOW_VWAP). The last two are merged into
FLOW_MOMENTUM_TRADER; `normalize_trader_code()` maps the old codes so stored sessions and trades keep working.
"""
from typing import Any

TRADER_FIB_GOLDEN = "FIB_GOLDEN_TRADER"
TRADER_FLOW_MOMENTUM = "FLOW_MOMENTUM_TRADER"
# 17 Nov 2026: the Commodity Desk (modules/commodity_desk) -- specialist sub-agents + an LLM head trader for MCX
# crude / natural gas / gold / silver. It owns the DESK_* setups. Like every finder it follows the session's own
# Upstox switch (the user may also act on its picks with another broker).
TRADER_COMMODITY_DESK = "COMMODITY_DESK_TRADER"
DESK_SETUP_PREFIX = "DESK_"

ALL_PRESET_TRADER_CODES: tuple[str, ...] = (TRADER_FIB_GOLDEN, TRADER_FLOW_MOMENTUM, TRADER_COMMODITY_DESK)
# what an old session with no / unknown traders stored means: the original two (never the Commodity Desk)
DEFAULT_PRESET_TRADER_CODES: tuple[str, ...] = (TRADER_FIB_GOLDEN, TRADER_FLOW_MOMENTUM)
# 17 Nov 2026: the session managers. Their duty is the same for INDEX and COMMODITY sessions, so there is no commodity
# manager: a session picks one of these, and its opportunities come from the finders that cover its scope.
SESSION_MANAGER_CODES: tuple[str, ...] = (TRADER_FLOW_MOMENTUM, TRADER_FIB_GOLDEN)
OPTION_TYPES: tuple[str, ...] = ("INDEX", "COMMODITY")

LEGACY_TRADER_CODES: dict[str, str] = {
    "ORB_WAVE_TRADER": TRADER_FLOW_MOMENTUM,
    "FLOW_VWAP_TRADER": TRADER_FLOW_MOMENTUM,
}

FIB_SETUP = "FIB_GOLDEN_POCKET"
_FIB_KEYWORDS = ("fib", "golden pocket", "golden-pocket", "retracement")

TRADER_PRESETS: list[dict[str, Any]] = [
    {
        "code": TRADER_FIB_GOLDEN,
        "name": "Fib Golden-Pocket Trader",
        "shortLabel": "FIB + OI + VOL",
        "badgeColor": "cyan",
        "methodology": "0.50-0.618 pullback of an impulse swing, confirmed by option-chain OI and futures volume",
        "entryLogic": (
            "Finds an impulse swing of at least 3 ATR on the 5-minute chart, waits for the pullback into the "
            "0.50-0.618 pocket and a 5-minute close turning back with the swing. Enters only when the option chain "
            "confirms (OI wall behind the stop, no OI wall blocking the target) and volume confirms (quiet pullback, "
            "active turn bar)."
        ),
        "trailLogic": (
            "Stop behind the 0.786 retracement. Waits for 80% of the move to the swing high before locking half the "
            "profit, then steps the target to the 1.272 and 1.618 extensions while momentum holds."
        ),
        "strategies": ["FIB_GOLDEN_POCKET"],
        "optionTypes": ["INDEX"],
        "drivers": "Mostly national: NSE option chain OI, futures volume, FII flow, domestic news",
        "checks": [
            "Pullback into the 0.50-0.618 pocket of a 3 ATR swing",
            "Price action: a corrective pullback, then a pin bar, engulfing or inside-bar break at the pocket",
            "Option-chain OI: wall behind the stop, none blocking the target",
            "Volume: quiet pullback, active turn bar",
        ],
        "liveOnly": False,
        "sortOrder": 2,
    },
    {
        "code": TRADER_FLOW_MOMENTUM,
        "name": "Flow & Momentum Trader",
        "shortLabel": "FLOW + MOMENTUM",
        "badgeColor": "green",
        "methodology": "Noise-area breakouts and institutional flow, held with an R-multiple trail (no fixed target)",
        "entryLogic": (
            "Takes the engine's breakout and flow setups: noise breakout, FII open drive, late-day "
            "momentum, plus VWAP pullback / range breakout / gap-and-go inside an active breakout on the same side."
        ),
        "trailLogic": (
            "Momentum setups: stop to breakeven at +1.5R, then trail 2R under the peak, no fixed target. Other "
            "entries: step guard (+30% of the move locked at 50% progress, +50% at 80%)."
        ),
        "strategies": [
            "NOISE_BREAKOUT",
            "FII_OPEN_DRIVE",
            "LATE_DAY_MOMENTUM",
            "VWAP_PULLBACK",
            "RANGE_BREAKOUT",
            "GAP_GO",
        ],
        "optionTypes": ["INDEX"],
        "drivers": "Mostly national: FII index-futures positioning, NSE dealer gamma, noise area, RBI / domestic news",
        "checks": [
            "Noise-area breakout, FII open drive, late-day momentum",
            "VWAP pullback / range breakout only inside an active breakout",
            "Day type, dealer gamma and 1-minute timing agree",
        ],
        "liveOnly": False,
        "sortOrder": 1,
    },
    {
        "code": TRADER_COMMODITY_DESK,
        "name": "Commodity Desk",
        "shortLabel": "DESK + AGENTS",
        "badgeColor": "amber",
        "methodology": "MCX desk: clock, structure, option-chain and news sub-agents report; an LLM head trader decides",
        "entryLogic": (
            "Sub-agents read the MCX session clock (US / London hours, EIA and US data releases), the 1/5/15-minute "
            "futures structure, the live option chain and the news. They propose trend pullbacks, fresh range "
            "breakouts and Fib pockets; a code risk gate refuses unsafe ones; the head trader writes its reasoning "
            "and takes one setup or waits. A TAKE trades only if it still holds at the next scan."
        ),
        "trailLogic": "Momentum management: stop to breakeven at +1.5R, then trail 2R under the peak.",
        "strategies": ["DESK_TREND_PULLBACK", "DESK_RANGE_BREAK", "DESK_FIB_POCKET"],
        "optionTypes": ["COMMODITY"],
        "drivers": "International: US / London session hours, EIA and US data, dollar, global news",
        "checks": [
            "Session clock: MCX phase (Asia / Europe / US open), EIA and US data releases",
            "Price structure on 1, 5 and 15-minute futures: trend pullback, fresh range break, Fib pocket",
            "Option chain of the traded expiry: PCR, OI walls, ATM liquidity",
            "News: Research Engine read and sudden-move explanations",
            "Code risk gate, then an LLM head trader writes its reasoning and takes one setup or waits",
        ],
        "liveOnly": True,
        "sortOrder": 3,
    },
]

_PRESET_BY_CODE: dict[str, dict[str, Any]] = {p["code"]: p for p in TRADER_PRESETS}


def normalize_trader_code(code: str | None) -> str | None:
    """Current trader code for `code` (old three-trader codes are mapped), or None when it is not a trader code."""
    if not code:
        return None
    c = LEGACY_TRADER_CODES.get(code, code)
    return c if c in _PRESET_BY_CODE else None


def normalize_trader_codes(codes: list[str] | None) -> list[str]:
    """De-duplicated current codes in preset order; an empty / unknown list means the original two traders."""
    wanted = {normalize_trader_code(c) for c in (codes or [])}
    out = [c for c in ALL_PRESET_TRADER_CODES if c in wanted]
    return out or list(DEFAULT_PRESET_TRADER_CODES)


def get_trader_preset(code: str | None) -> dict[str, Any]:
    """Preset metadata for `code` (old codes accepted); unknown codes fall back to the Flow & Momentum trader."""
    return _PRESET_BY_CODE[normalize_trader_code(code) or TRADER_FLOW_MOMENTUM]


def assign_trader_for_opportunity(strategy: str | None, confidence: int = 70, reward_risk: float = 1.5) -> str:
    """Which trader owns an opportunity: the Fib trader for the Fib golden-pocket setup (by setup name, or a cited
    strategy that names it), the Flow & Momentum trader for everything else. `confidence` / `reward_risk` are kept
    for call compatibility; ownership no longer depends on them."""
    del confidence, reward_risk
    s = (strategy or "").strip()
    if s.upper().startswith(DESK_SETUP_PREFIX):
        return TRADER_COMMODITY_DESK
    if s.upper() == FIB_SETUP or any(k in s.lower() for k in _FIB_KEYWORDS):
        return TRADER_FIB_GOLDEN
    return TRADER_FLOW_MOMENTUM


# A session is run by one session manager; each manager hands its session to one trader (same code). The autopsy is
# the manager's sub-agent (modules/autopsy, sessions/service/manager_agents.py). Names match the frontend traderMeta.
SESSION_MANAGER_NAME: dict[str, str] = {
    TRADER_FLOW_MOMENTUM: "Indian Quant Desk",
    TRADER_FIB_GOLDEN: "My Experience",
    TRADER_COMMODITY_DESK: "Commodity Desk",
}


def routes_to_broker(session_routes: bool, strategy: str | None = None) -> bool:
    """Whether a pick becomes a real Upstox order: exactly when its session routes through Upstox. Every finder,
    the Commodity Desk included, follows the session's switch (17 Nov 2026: the desk is no longer simulated-only --
    its picks are acted on, with Upstox or with another broker by hand)."""
    del strategy
    return bool(session_routes)


def default_option_types(code: str | None) -> list[str]:
    """The code default of a finder's optionTypes (the opportunity_finders table may override it)."""
    c = normalize_trader_code(code)
    return list(_PRESET_BY_CODE[c]["optionTypes"]) if c else ["INDEX"]


def normalize_manager_code(code: str | None) -> str | None:
    """A session manager code (old Commodity Desk sessions map to Indian Quant Desk), or None when unknown."""
    c = normalize_trader_code(code)
    if c == TRADER_COMMODITY_DESK:
        return TRADER_FLOW_MOMENTUM
    return c if c in SESSION_MANAGER_CODES else None


def manager_name(code: str | None) -> str:
    return SESSION_MANAGER_NAME.get(normalize_trader_code(code) or "", code or "session manager")


def session_finder_codes(finders: list[str] | None, traders: list[str] | None = None) -> list[str]:
    """The finders that feed a session: its `finders` (normalized, preset order); sessions saved before 0030 had
    none and used the finders named in `traders`."""
    wanted = {normalize_trader_code(c) for c in (finders or [])} - {None}
    out = [c for c in ALL_PRESET_TRADER_CODES if c in wanted]
    return out or normalize_trader_codes(traders)
