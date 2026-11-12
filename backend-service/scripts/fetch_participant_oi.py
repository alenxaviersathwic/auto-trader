"""Backfill NSE participant-wise OI (FII / client / pro positioning) for the opening-bias study.

Run inside the backend container (it has NSE access):
    docker exec -i autotrader_backend python - < backend-service/scripts/fetch_participant_oi.py
Files land where positioning.fetch() saves them; already-saved days are skipped.
"""
import asyncio
import sys
from datetime import date, timedelta

sys.path.insert(0, "/app")
from app.modules.opportunities.service import positioning as pos  # noqa: E402

START = date(2026, 5, 1)


async def main() -> None:
    d, got, miss = START, 0, 0
    while d <= date.today():
        if d.weekday() < 5:
            p = await pos.fetch(d)
            got, miss = (got + 1, miss) if p else (got, miss + 1)
            print(f"{d} {'ok' if p else '-'}", flush=True)
            await asyncio.sleep(0.4)
        d += timedelta(days=1)
    print(f"done: {got} days saved, {miss} missing (holidays / not published)")


asyncio.run(main())
