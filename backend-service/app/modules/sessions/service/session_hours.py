"""
Trading hours of a session (IST). Pure functions, no I/O.

  start  default = now when the session is created at/after 09:25, otherwise 09:15 (market open)
  close  default = 15:45 for INDEX, 23:00 for COMMODITY (MCX trades in the evening)
The loop does not offer anything before `start` and closes the session at `close`.
"""
import re
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
LATE_START_AFTER = time(9, 25)  # created at/after this time: start right now instead of at the open
DEFAULT_CLOSE = time(15, 45)
COMMODITY_CLOSE = time(23, 0)
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def default_close(scope: str = "INDEX") -> time:
    return COMMODITY_CLOSE if (scope or "").upper() == "COMMODITY" else DEFAULT_CLOSE


def parse_hhmm(value: str) -> time:
    if not HHMM.match(value or ""):
        raise ValueError(f"time must be HH:MM (24 hour), got {value!r}")
    h, m = value.split(":")
    return time(int(h), int(m))


def at(trade_date: str, t: time) -> datetime:
    """`t` on `trade_date`, read as IST, returned in UTC."""
    y, mo, d = (int(x) for x in trade_date.split("-"))
    return datetime(y, mo, d, t.hour, t.minute, tzinfo=_IST).astimezone(UTC)


def default_start(trade_date: str, now: datetime | None = None) -> datetime:
    """Now (whole minute) when the session is created for today at/after 09:25 IST; otherwise 09:15 on its date."""
    now = (now or datetime.now(UTC)).astimezone(_IST)
    if trade_date == now.date().isoformat() and now.time() >= LATE_START_AFTER:
        return now.replace(second=0, microsecond=0).astimezone(UTC)
    return at(trade_date, MARKET_OPEN)


def resolve(trade_date: str, start_time: str | None, close_time: str | None,
            now: datetime | None = None, scope: str = "INDEX") -> tuple[datetime, datetime]:
    """(startAt, closeAt) for a session: the given HH:MM values, else the defaults for its scope. Raises ValueError when
    close is not after start."""
    start = at(trade_date, parse_hhmm(start_time)) if start_time else default_start(trade_date, now)
    close = at(trade_date, parse_hhmm(close_time)) if close_time else at(trade_date, default_close(scope))
    if close <= start:
        raise ValueError(
            f"close time ({close.astimezone(_IST):%H:%M}) must be after start time ({start.astimezone(_IST):%H:%M})"
        )
    return start, close
