"""
Scheduled macro events that a short-premium / momentum day must respect (institutional-strategy review, 11 Nov 2026:
"no short premium into RBI MPC, Union Budget, US CPI/FOMC").

  RBI_MPC      the RBI policy announcement day (3rd day of the MPC meeting, ~10:00 IST)
  BUDGET       Union Budget day (1 February)
  US_CPI       US CPI release (08:30 ET = 19:00/18:00 IST) -> the NEXT India session opens on it
  FOMC         FOMC decision (14:00 ET = 00:30/23:30 IST) -> the NEXT India session opens on it

Sources: RBI MPC FY27 calendar (RBI press release, reported by Upstox News); FOMC / CPI from the Fed / BLS schedules
(as listed on centralbank.watch and fedratecalc.com, checked 11 Nov 2026). Re-verify every quarter and add new
dates: an event missing from here is simply not blocked.
"""
from datetime import date, timedelta

EVENTS: dict[str, tuple[str, ...]] = {
    # RBI MPC policy announcement (FY 2026-27)
    "2026-04-08": ("RBI_MPC",), "2026-06-05": ("RBI_MPC",), "2026-08-05": ("RBI_MPC",),
    "2026-10-07": ("RBI_MPC",), "2026-12-04": ("RBI_MPC",), "2027-02-05": ("RBI_MPC",),
    # Union Budget
    "2027-02-01": ("BUDGET",),
    # US events (US calendar date; they land on the NEXT India session)
    "2026-12-09": ("FOMC",), "2026-12-10": ("US_CPI",),
    "2027-01-27": ("FOMC",), "2027-03-17": ("FOMC",),
}
_US = {"FOMC", "US_CPI"}


def event_tags(d: date) -> list[str]:
    """EVENT_* tags for India session date `d`: Indian events on the day, US events from the previous calendar day(s)
    (a Monday session also sees Friday/Saturday US events)."""
    tags = [f"EVENT_{e}" for e in EVENTS.get(d.isoformat(), ()) if e not in _US]
    back = 3 if d.weekday() == 0 else 1
    for i in range(1, back + 1):
        tags += [f"EVENT_{e}_OVERNIGHT" for e in EVENTS.get((d - timedelta(days=i)).isoformat(), ()) if e in _US]
    return tags
