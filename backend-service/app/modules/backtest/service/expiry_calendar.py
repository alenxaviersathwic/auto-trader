"""
Which option series was live on a given historical trading day, for a given underlying.

No historical option-chain exists (Upstox has no chain-history API -- see docs/05 section on
`chain_recorder.py`), so a backtest over a past date can't just ask the live chain "what expired
that day". This re-derives it from the weekly/monthly calendar in docs/02-derivatives-and-expiry-
calendar.md, plus the holiday-shift rule (an expiry weekday that falls on a trading holiday moves
to the previous trading day) using the SAME holiday table the live day-context tags use.

  NIFTY       weekly Tuesday (NSE), monthly = last Tuesday
  SENSEX      weekly Thursday (BSE), monthly = last Thursday
  BANKNIFTY, FINNIFTY, MIDCPNIFTY   monthly only, last Tuesday (NSE)
"""
from datetime import date, timedelta

from app.modules.opportunities.service.day_context import is_trading_holiday, previous_trading_day

WEEKLY_WEEKDAY = {"NIFTY": 1, "SENSEX": 3}  # Monday=0 ... Tuesday=1, Thursday=3
MONTHLY_WEEKDAY = {"NIFTY": 1, "SENSEX": 3, "BANKNIFTY": 1, "FINNIFTY": 1, "MIDCPNIFTY": 1}
EXCHANGE = {"NIFTY": "NSE", "SENSEX": "BSE", "BANKNIFTY": "NSE", "FINNIFTY": "NSE", "MIDCPNIFTY": "NSE"}


def _shift_for_holiday(d: date, exchange: str) -> date:
    """An expiry weekday that is a trading holiday moves to the previous trading day."""
    return previous_trading_day(d, exchange) if is_trading_holiday(d, exchange) else d


def _next_weekday_on_or_after(d: date, weekday: int) -> date:
    return d + timedelta(days=(weekday - d.weekday()) % 7)


def _last_weekday_of_month(d: date, weekday: int) -> date:
    if d.month == 12:
        nxt = date(d.year + 1, 1, 1)
    else:
        nxt = date(d.year, d.month + 1, 1)
    last_day = nxt - timedelta(days=1)
    return last_day - timedelta(days=(last_day.weekday() - weekday) % 7)


def expiry_for(code: str, as_of: date) -> date | None:
    """The expiry date of the series that was LIVE (nearest, not yet expired) on `as_of`.

    For NIFTY/SENSEX: the next weekly expiry on or after `as_of`, holiday-shifted. If that shift
    moves it to or before `as_of` itself (the live contract already expired that day), roll to the
    following week. For BANKNIFTY: this month's monthly expiry, holiday-shifted, rolling to next
    month if the shift puts it at or before `as_of`."""
    exchange = EXCHANGE.get(code)
    if not exchange:
        return None
    if code in WEEKLY_WEEKDAY:
        candidate = _shift_for_holiday(_next_weekday_on_or_after(as_of, WEEKLY_WEEKDAY[code]), exchange)
        if candidate < as_of:
            nxt_week = as_of + timedelta(days=(WEEKLY_WEEKDAY[code] - as_of.weekday()) % 7 + 7)
            candidate = _shift_for_holiday(nxt_week, exchange)
        return candidate
    if code in MONTHLY_WEEKDAY:
        candidate = _shift_for_holiday(_last_weekday_of_month(as_of, MONTHLY_WEEKDAY[code]), exchange)
        if candidate < as_of:
            nxt_month = date(as_of.year + (as_of.month == 12), as_of.month % 12 + 1, 1)
            candidate = _shift_for_holiday(_last_weekday_of_month(nxt_month, MONTHLY_WEEKDAY[code]), exchange)
        return candidate
    return None
