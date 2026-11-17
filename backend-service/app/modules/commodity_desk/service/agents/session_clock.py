"""
Session-clock sub-agent: where the MCX day stands for this commodity and what scheduled event is near.

MCX follows the world, not the NSE clock. Phases are computed from the real London / New York wall clocks (zoneinfo), so
the daylight-saving shift (MCX close 23:30 <-> 23:55 IST, US data 18:00 <-> 19:00 IST) is always right:
  ASIA      09:00 IST -> London 08:00   thin, smaller moves (crude / natgas follow the overnight US range)
  EUROPE    London 08:00 -> New York 08:30   Europe trades; gold / silver react to European data
  US_OPEN   New York 08:30 -> 11:30   US data + the NYMEX / COMEX open: the day's main liquidity and moves
  US_LATE   New York 11:30 -> MCX close
  CLOSING   the last 30 minutes before the MCX close: no new entries

Scheduled releases (New York time; the agent says CAUTION 20 min before to 15 min after, BLOCK in the last 10 min):
  CRUDEOIL    EIA Weekly Petroleum Status Report, Wednesday 10:30
  NATURALGAS  EIA Weekly Natural Gas Storage Report, Thursday 10:30
  all         US CPI 08:30 / FOMC 14:00 on the dates in opportunity_finder/service/event_calendar.py;
              US jobs report (first Friday of the month) 08:30 for GOLD / SILVER
A holiday-shifted EIA release is not modelled: on those weeks the warning comes on the usual day.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.modules.opportunity_finder.service.event_calendar import EVENTS

IST, NY, LDN = ZoneInfo("Asia/Kolkata"), ZoneInfo("America/New_York"), ZoneInfo("Europe/London")
NO_ENTRY_BEFORE_CLOSE_MIN = 30
EVENT_BEFORE_MIN, EVENT_AFTER_MIN, EVENT_BLOCK_MIN = 20, 15, 10


def _at(day_ny: datetime, hh: int, mm: int, tz: ZoneInfo) -> datetime:
    return datetime.combine(day_ny.date(), time(hh, mm), tzinfo=tz).astimezone(IST)


def _events(code: str, now: datetime) -> list[tuple[str, datetime]]:
    """Scheduled releases for `code` on the New York calendar day that overlaps `now` (and the day before, for the
    evening of an Asian morning). Returned in IST."""
    out: list[tuple[str, datetime]] = []
    ny_now = now.astimezone(NY)
    for d in (ny_now - timedelta(days=1), ny_now):
        if code == "CRUDEOIL" and d.weekday() == 2:
            out.append(("EIA crude inventories", _at(d, 10, 30, NY)))
        if code == "NATURALGAS" and d.weekday() == 3:
            out.append(("EIA natural-gas storage", _at(d, 10, 30, NY)))
        if code in ("GOLD", "SILVER") and d.weekday() == 4 and d.day <= 7:
            out.append(("US jobs report", _at(d, 8, 30, NY)))
        for e in EVENTS.get(d.date().isoformat(), ()):
            if e == "US_CPI":
                out.append(("US CPI", _at(d, 8, 30, NY)))
            elif e == "FOMC":
                out.append(("FOMC decision", _at(d, 14, 0, NY)))
    return out


def mcx_close(now: datetime) -> datetime:
    ny = now.astimezone(NY)
    hhmm = (23, 55) if ny.dst() and ny.dst().total_seconds() > 0 else (23, 30)
    return now.astimezone(IST).replace(hour=hhmm[0], minute=hhmm[1], second=0, microsecond=0)


def phase(now: datetime) -> str:
    n = now.astimezone(IST)
    if mcx_close(n) - n <= timedelta(minutes=NO_ENTRY_BEFORE_CLOSE_MIN):
        return "CLOSING"
    ldn_open = _at(n.astimezone(LDN), 8, 0, LDN)
    us_open = _at(n.astimezone(NY), 8, 30, NY)
    us_mid = _at(n.astimezone(NY), 11, 30, NY)
    if n < ldn_open:
        return "ASIA"
    if n < us_open:
        return "EUROPE"
    if n < us_mid:
        return "US_OPEN"
    return "US_LATE"


PHASE_TEXT = {
    "ASIA": "Asian hours: thin MCX liquidity, moves usually stay inside the overnight US range",
    "EUROPE": "European hours: liquidity building ahead of the US",
    "US_OPEN": "US data and the NYMEX / COMEX open: the main liquidity window of the MCX day",
    "US_LATE": "late US session: trend days extend, range days fade",
    "CLOSING": f"last {NO_ENTRY_BEFORE_CLOSE_MIN} minutes before the MCX close: no new entries",
}


def read(code: str, now: datetime, dte: int | None = None) -> dict[str, Any]:
    n = now.astimezone(IST)
    ph = phase(n)
    stance, facts = "NEUTRAL", [PHASE_TEXT[ph]]
    if ph == "CLOSING":
        stance = "BLOCK"
    nearest: dict[str, Any] | None = None
    for name, at in sorted(_events(code, n), key=lambda x: abs((x[1] - n).total_seconds())):
        mins = (at - n).total_seconds() / 60
        if -EVENT_AFTER_MIN <= mins <= EVENT_BEFORE_MIN:
            nearest = {"event": name, "at": at.strftime("%H:%M"), "minutes": round(mins)}
            if 0 <= mins <= EVENT_BLOCK_MIN:
                stance = "BLOCK"
                facts.append(f"{name} at {at:%H:%M} IST in {mins:.0f} min: no new entry into the release")
            else:
                stance = "CAUTION" if stance != "BLOCK" else stance
                facts.append(f"{name} at {at:%H:%M} IST ({'in' if mins >= 0 else ''} {abs(mins):.0f} min"
                             f"{' ago' if mins < 0 else ''}): expect a whipsaw")
            break
        if 0 < mins <= 6 * 60:
            facts.append(f"later today: {name} at {at:%H:%M} IST")
            break
    if dte == 0:
        facts.append("front-month options expire today: only the next expiry is traded")
    summary = facts[0] if stance == "NEUTRAL" else facts[-1] if nearest else facts[0]
    return {"agent": "clock", "name": "Session clock", "stance": stance, "score": 0, "summary": summary,
            "facts": facts, "data": {"phase": ph, "event": nearest, "mcxClose": mcx_close(n).strftime("%H:%M")}}
