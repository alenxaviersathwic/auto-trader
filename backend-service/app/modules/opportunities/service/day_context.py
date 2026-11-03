"""
Day-context tags: cheap, code-computed labels for "what kind of trading day is this"
(DAY_MONDAY, AFTER_HOLIDAY, EXPIRY_DAY, ...). These are matched against a Strategy's own
`tags` field (already on the Strategy entity) so a strategy tagged for conditions that fit
today gets a small confidence nudge in opportunities/graph/nodes.py::validate() -- the same
pattern as setup_adjustment/buildup_adjustment, just keyed by day context instead of market
structure.

Holiday table is NSE/BSE's published 2026 trading-holiday circular (cross-checked against two
independent sources on 2026-11-03). Re-verify every January against the exchange's own circular,
same as the "Keeping this file correct" note in docs/02-derivatives-and-expiry-calendar.md --
this list will silently go stale otherwise.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
WEEKDAY_TAGS = ("DAY_MONDAY", "DAY_TUESDAY", "DAY_WEDNESDAY", "DAY_THURSDAY", "DAY_FRIDAY")

# NSE/BSE trading holidays, calendar year 2026. MCX trades a shortened evening-only session on the
# dates in MCX_EVENING_ONLY_2026 (morning segment closed, evening ~17:00-23:30/23:55 IST open);
# everywhere else in this list MCX is fully closed too.
NSE_BSE_HOLIDAYS_2026: dict[str, str] = {
    "2026-01-26": "Republic Day",
    "2026-03-03": "Holi",
    "2026-03-26": "Ram Navami",
    "2026-03-31": "Mahavir Jayanti",
    "2026-04-03": "Good Friday",
    "2026-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
    "2026-05-01": "Maharashtra Day",
    "2026-05-28": "Bakri Id",
    "2026-06-26": "Muharram",
    "2026-09-14": "Ganesh Chaturthi",
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-10-20": "Dussehra",
    "2026-11-10": "Diwali Balipratipada",
    "2026-11-24": "Prakash Gurpurb Sri Guru Nanak Dev",
    "2026-12-25": "Christmas",
}
MCX_EVENING_ONLY_2026 = {
    "2026-03-03", "2026-03-26", "2026-03-31", "2026-04-14", "2026-05-01", "2026-05-28",
    "2026-06-26", "2026-09-14", "2026-10-20", "2026-11-10", "2026-11-24",
}


def is_trading_holiday(d: date, exchange: str = "NSE") -> bool:
    """Full-day exchange holiday. MCX's evening-only dates are NOT a full holiday (its session
    still trades in the evening), so they return False here -- use is_mcx_evening_only() for those."""
    iso = d.isoformat()
    if iso not in NSE_BSE_HOLIDAYS_2026:
        return False
    if exchange == "MCX" and iso in MCX_EVENING_ONLY_2026:
        return False
    return True


def is_mcx_evening_only(d: date) -> bool:
    return d.isoformat() in MCX_EVENING_ONLY_2026


def _is_closed_day(d: date, exchange: str) -> bool:
    return d.weekday() >= 5 or is_trading_holiday(d, exchange)


def previous_trading_day(d: date, exchange: str = "NSE") -> date:
    p = d - timedelta(days=1)
    while _is_closed_day(p, exchange):
        p -= timedelta(days=1)
    return p


def next_trading_day(d: date, exchange: str = "NSE") -> date:
    n = d + timedelta(days=1)
    while _is_closed_day(n, exchange):
        n += timedelta(days=1)
    return n


def compute_calendar_tags(now: datetime | None = None, exchange: str = "NSE") -> list[str]:
    """Pure-calendar tags: weekday, holiday-adjacency, month-end. No market data needed."""
    now = now or datetime.now(IST)
    today = now.date()
    tags: list[str] = []
    if today.weekday() < 5:
        tags.append(WEEKDAY_TAGS[today.weekday()])
    # AFTER_HOLIDAY: yesterday (or the most recent non-weekend day before today) was a holiday.
    y = today - timedelta(days=1)
    while y.weekday() >= 5:
        y -= timedelta(days=1)
    if is_trading_holiday(y, exchange):
        tags.append("AFTER_HOLIDAY")
    # BEFORE_HOLIDAY: the next trading day is a holiday-shortened gap (tomorrow, skipping weekend, is a holiday).
    t = today + timedelta(days=1)
    while t.weekday() >= 5:
        t += timedelta(days=1)
    if is_trading_holiday(t, exchange):
        tags.append("BEFORE_HOLIDAY")
    if exchange == "MCX" and is_mcx_evening_only(today):
        tags.append("MCX_EVENING_ONLY")
    # MONTH_END: no more trading days left in this calendar month after today.
    if next_trading_day(today, exchange).month != today.month:
        tags.append("MONTH_END")
    return tags


def compute_expiry_tags(today: date, chains: list[dict]) -> list[str]:
    """EXPIRY_DAY / EXPIRY_WEEK from the already-fetched option chain's own expiry date --
    never hardcode a weekday-per-underlying rule here (NSE moved weekly expiry weekdays in
    Sep 2025; see docs/02-derivatives-and-expiry-calendar.md)."""
    tags: list[str] = []
    expiries = [c["expiry"] for c in (chains or []) if c.get("expiry")]
    if not expiries:
        return tags
    near = min(expiries)
    try:
        near_date = date.fromisoformat(near)
    except ValueError:
        return tags
    if near_date == today:
        tags.append("EXPIRY_DAY")
    iso_today = today.isocalendar()
    iso_near = near_date.isocalendar()
    if (iso_today[0], iso_today[1]) == (iso_near[0], iso_near[1]):
        tags.append("EXPIRY_WEEK")
    return tags
