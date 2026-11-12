"""FII_OPEN_DRIVE -- opening call buy when FIIs added index-futures longs the previous day (12 Nov 2026 study).

Rule
  previous session's NSE participant OI: FII index-futures net (long - short) went UP vs the session before
  -> buy an ITM next-expiry CE between ENTRY_FROM and ENTRY_TO (first minutes after the 5-minute open block),
     catastrophic stop STOP_PCT below spot, exit at EXIT_HHMM (time exit, no tight stop: tight stops lost money).
  CE only: the mirror-image PE (FII net down) had no edge.

Evidence (logs/realdata6m, 127 sessions May-Nov 2026, model-priced at delta 0.7, Rs 250 cost per trade)
  NIFTY, 09:20 entry, 0.4% stop, 10:30 exit: 55 trades, 62% win, +Rs 49.7k, both halves positive (H1 +21k, H2 +28k)
  control -- CE on FII-net-DOWN days: average move ~0 (the signal, not the bull market, carries the edge)
  Caveats: CE-only in a mostly rising period; not yet priced from real option candles; ~55 independent days.

Switched by settings.FII_OPEN_CODES (comma list, "" = off). Not part of institutional_filters.MOMENTUM_SETUPS:
the 10:00-14:30 / initial-balance gates are for intraday momentum, this is an opening trade by design.
"""
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from app.modules.opportunities.service import positioning

NAME = "FII_OPEN_DRIVE"
IST = ZoneInfo("Asia/Kolkata")
ENTRY_FROM, ENTRY_TO = time(9, 20), time(9, 35)
EXIT_HHMM = time(10, 30)
STOP_PCT = 0.4
TARGET_R = 4.0  # nominal (menu needs a target); the trade exits on time / trail, not on this level


def enabled_codes() -> set[str]:
    from app.core.config.settings import settings  # lazy: importable without app config

    return {c.strip().upper() for c in (getattr(settings, "FII_OPEN_CODES", "") or "").split(",") if c.strip()}


def fii_net_change(today: date) -> tuple[float, str] | None:
    """(FII index-futures net change, as-of date) from the two latest saved files BEFORE `today`, or None."""
    hist = [(d, p) for d, p in positioning.load_saved(12, today) if d < today and "FII" in p]
    if len(hist) < 2:
        return None
    (_, q), (d1, p) = hist[-2], hist[-1]
    net = lambda z: z["FII"]["futLong"] - z["FII"]["futShort"]  # noqa: E731
    return net(p) - net(q), d1.isoformat()


def signal(code: str, spot: float | None, now: datetime | None = None,
           change: tuple[float, str] | None = None) -> dict[str, Any] | None:
    """The FII_OPEN_DRIVE setup for `code` right now, or None (off, outside the window, no data, FII net not up)."""
    if not spot or code.upper() not in enabled_codes():
        return None
    now = (now or datetime.now(IST)).astimezone(IST)
    if not (ENTRY_FROM <= now.time() <= ENTRY_TO):
        return None
    ch = change if change is not None else fii_net_change(now.date())
    if not ch or ch[0] <= 0:
        return None
    stop = spot * (1 - STOP_PCT / 100)
    risk = spot - stop
    return {"name": NAME, "side": "CE", "strength": 3, "family": "OPEN", "fixedStop": True,
            "entry": round(spot, 2), "stop": round(stop, 2), "target": round(spot + TARGET_R * risk, 2),
            "targetLevel": f"{TARGET_R:g}R", "rr": TARGET_R, "exitBy": EXIT_HHMM.strftime("%H:%M"),
            "reason": f"FIIs added {ch[0]:+,.0f} net index-futures contracts on {ch[1]}: opening CE, time exit "
                      f"{EXIT_HHMM:%H:%M}, stop {STOP_PCT:g}% below spot"}


def exit_at(strategy: str | None, day: date) -> datetime | None:
    """Mandatory time exit for this strategy on `day` (IST), or None."""
    if strategy != NAME:
        return None
    return datetime.combine(day, EXIT_HHMM, tzinfo=IST)
